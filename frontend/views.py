from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from datetime import timedelta, datetime, time
from django.contrib.auth.models import User

from core.models import (
    Profile, Category, Service, ProviderProfile, 
    Booking, Location, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability
)

# ============================================================================
# HOME & PUBLIC VIEWS
# ============================================================================

def home(request):
    """Página principal"""
    categories = Category.objects.all()
    featured_services = Service.objects.filter(available=True)[:6]
    
    context = {
        'categories': categories,
        'featured_services': featured_services,
    }
    return render(request, 'home.html', context)


@login_required
def services_list(request):
    """Listado de servicios con filtros mejorados"""
    services = Service.objects.filter(available=True).select_related('provider')
    categories = Category.objects.all()
    zones = Zone.objects.filter(active=True).order_by('name')
    
    # Filtros
    category_id = request.GET.get('category')
    search = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    zone_id = request.GET.get('zone')  # ← NUEVO FILTRO
    
    if category_id:
        services = services.filter(provider__provider_profile__category_id=category_id)
    
    if search:
        services = services.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    if min_price:
        services = services.filter(base_price__gte=min_price)
    
    if max_price:
        services = services.filter(base_price__lte=max_price)
    
    # Filtrar por zona
    if zone_id:
        services = services.filter(
            provider__provider_profile__coverage_zones__id=zone_id,
            provider__provider_profile__is_active=True  # Solo proveedores activos
        )
    
    # Filtrar solo proveedores activos y aprobados
    services = services.filter(
        provider__provider_profile__status='approved',
        provider__provider_profile__is_active=True
    )
    
    # Agregar rating promedio
    for service in services:
        rating = Review.objects.filter(
            booking__provider=service.provider
        ).aggregate(Avg('rating'))
        service.provider_rating = round(rating['rating__avg'] or 0, 1)
    
    context = {
        'services': services,
        'categories': categories,
        'zones': zones,
        'selected_zone': Zone.objects.filter(id=zone_id).first() if zone_id else None,
        'selected_category': Category.objects.filter(id=category_id).first() if category_id else None,
    }
    return render(request, 'services/list.html', context)


def service_detail(request, service_id):
    """Detalle de un servicio"""
    service = get_object_or_404(Service, id=service_id)
    
    # Reviews del proveedor
    reviews = Review.objects.filter(
        booking__provider=service.provider
    ).select_related('customer', 'booking')[:10]
    
    # Rating promedio
    rating_data = Review.objects.filter(
        booking__provider=service.provider
    ).aggregate(
        avg_rating=Avg('rating'),
        total=Count('id')
    )
    
    # Ubicaciones del usuario (si está logueado)
    user_locations = []
    if request.user.is_authenticated:
        user_locations = Location.objects.filter(customer=request.user)
    
    # Calcular costo total
    travel_cost = 0
    if hasattr(service.provider, 'provider_profile'):
        travel_cost = service.provider.provider_profile.avg_travel_cost
    
    total_cost = service.base_price + travel_cost
    
    context = {
        'service': service,
        'reviews': reviews,
        'provider_rating': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'user_locations': user_locations,
        'travel_cost': travel_cost,
        'total_cost': total_cost,
        'today': timezone.now().date(),
    }
    return render(request, 'services/detail.html', context)


def providers_list(request):
    """Listado de proveedores"""
    providers = ProviderProfile.objects.filter(
        status='approved'
    ).select_related('user', 'category').prefetch_related('coverage_zones')
    
    categories = Category.objects.all()
    
    # Filtros
    category_id = request.GET.get('category')
    search = request.GET.get('search')
    
    if category_id:
        providers = providers.filter(category_id=category_id)
    
    if search:
        providers = providers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Agregar ratings
    for provider in providers:
        rating_data = Review.objects.filter(
            booking__provider=provider.user
        ).aggregate(
            avg_rating=Avg('rating'),
            total=Count('id')
        )
        provider.rating_avg = round(rating_data['avg_rating'] or 0, 1)
        provider.total_reviews = rating_data['total']
    
    context = {
        'providers': providers,
        'categories': categories,
    }
    return render(request, 'providers/list.html', context)


def provider_profile(request, provider_id):
    """Perfil público de un proveedor"""
    provider = get_object_or_404(User, id=provider_id)
    provider_profile = get_object_or_404(ProviderProfile, user=provider)
    
    # Servicios del proveedor
    services = Service.objects.filter(provider=provider, available=True)
    
    # Reviews
    reviews = Review.objects.filter(
        booking__provider=provider
    ).select_related('customer', 'booking')[:10]
    
    # Rating promedio
    rating_data = Review.objects.filter(
        booking__provider=provider
    ).aggregate(
        avg_rating=Avg('rating'),
        total=Count('id')
    )
    
    # Trabajos completados
    completed_bookings = Booking.objects.filter(
        provider=provider,
        status='completed'
    ).count()
    
    context = {
        'provider': provider,
        'provider_profile': provider_profile,
        'services': services,
        'reviews': reviews,
        'rating_avg': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'completed_bookings': completed_bookings,
    }
    return render(request, 'providers/profile.html', context)


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

def login_view(request):
    """Login de usuario"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
            
            # Redirigir a next o dashboard
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'auth/login.html')


def register_view(request):
    """Registro de cliente"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        
        # Validaciones
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'auth/register.html')
        
        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Crear perfil
        Profile.objects.create(
            user=user,
            phone=phone,
            role='customer'
        )
        
        # Login automático
        login(request, user)
        messages.success(request, '¡Registro exitoso! Bienvenido a Liberi')
        
        return redirect('dashboard')
    
    return render(request, 'auth/register.html')


def register_provider_view(request):
    """Registro de proveedor"""
    categories = Category.objects.all()
    
    if request.method == 'POST':
        # Datos de usuario
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        
        # Datos de proveedor
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        coverage_zones = request.POST.get('coverage_zones', '').split(',')
        coverage_zones = [zone.strip() for zone in coverage_zones if zone.strip()]
        avg_travel_cost = request.POST.get('avg_travel_cost', 0)
        
        # Validaciones
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register_provider.html', {'categories': categories})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register_provider.html', {'categories': categories})
        
        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Crear perfil
        Profile.objects.create(
            user=user,
            phone=phone,
            role='provider'
        )
        
        # Crear perfil de proveedor
        provider_profile = ProviderProfile.objects.create(
            user=user,
            category_id=category_id,
            description=description,
            # NOTA: Quita 'coverage_zones' de aquí
            avg_travel_cost=avg_travel_cost,
            status='pending'
        )

        zone_objects = []
        for zone_name in coverage_zones:
            # get_or_create es una buena práctica para asegurar que la zona exista
            zone, created = Zone.objects.get_or_create(name=zone_name)
            zone_objects.append(zone)

        # Paso B: Usar .set() para establecer la relación
        provider_profile.coverage_zones.set(zone_objects)
        
        # Login automático
        login(request, user)
        messages.success(request, '¡Registro exitoso! Tu perfil está en revisión')
        
        return redirect('dashboard')
    
    context = {
        'categories': categories,
    }
    return render(request, 'auth/register_provider.html', context)


def logout_view(request):
    """Logout"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('home')


# ============================================================================
# DASHBOARD VIEWS
# ============================================================================

@login_required
def dashboard(request):
    """Dashboard principal - redirige según rol"""
    if not hasattr(request.user, 'profile'):
        messages.error(request, 'Tu perfil no está completo')
        return redirect('home')
    
    if request.user.profile.role == 'provider':
        return dashboard_provider(request)
    else:
        return dashboard_customer(request)


@login_required
def dashboard_customer(request):
    """Dashboard de cliente"""
    # Estadísticas
    bookings = Booking.objects.filter(customer=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    completed_bookings = bookings.filter(status='completed').count()
    
    # Reservas recientes
    recent_bookings = bookings.order_by('-created_at')[:5]
    
    # Reservas pendientes de reseña
    pending_reviews = bookings.filter(
        status='completed'
    ).exclude(
        id__in=Review.objects.values_list('booking_id', flat=True)
    )[:5]
    
    # Ubicaciones
    locations = Location.objects.filter(customer=request.user)
    total_locations = locations.count()
    
    # Categorías
    categories = Category.objects.all()
    
    context = {
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'recent_bookings': recent_bookings,
        'pending_reviews': pending_reviews,
        'locations': locations,
        'total_locations': total_locations,
        'categories': categories,
    }
    return render(request, 'dashboard/customer.html', context)


@login_required
def dashboard_provider(request):
    """Dashboard de proveedor"""
    # Verificar que tenga perfil de proveedor
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('home')
    
    provider_profile = request.user.provider_profile
    
    # Estadísticas
    bookings = Booking.objects.filter(provider=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    completed_bookings = bookings.filter(status='completed').count()
    
    # Calcular ganancias totales
    total_earnings = bookings.filter(
        status='completed',
        payment_status='paid'
    ).aggregate(total=Sum('total_cost'))['total'] or 0
    
    # Reservas recientes
    recent_bookings = bookings.order_by('-created_at')[:5]
    
    # Servicios
    services = Service.objects.filter(provider=request.user)
    
    # Reviews recientes
    recent_reviews = Review.objects.filter(
        booking__provider=request.user
    ).select_related('customer', 'booking').order_by('-created_at')[:5]
    
    # Rating promedio
    rating_data = Review.objects.filter(
        booking__provider=request.user
    ).aggregate(
        avg_rating=Avg('rating'),
        total=Count('id')
    )
    
    context = {
        'provider_profile': provider_profile,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'total_earnings': total_earnings,
        'recent_bookings': recent_bookings,
        'services': services,
        'recent_reviews': recent_reviews,
        'rating_avg': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
    }
    return render(request, 'dashboard/provider.html', context)


# ============================================================================
# BOOKING VIEWS
# ============================================================================

@login_required
def bookings_list(request):
    """Lista de reservas del usuario"""
    user = request.user
    
    if user.profile.role == 'customer':
        bookings = Booking.objects.filter(customer=user)
    elif user.profile.role == 'provider':
        bookings = Booking.objects.filter(provider=user)
    else:
        bookings = Booking.objects.none()
    
    bookings = bookings.select_related('customer', 'provider', 'location').order_by('-created_at')
    
    # Separar por estado
    pending_bookings = bookings.filter(status='pending')
    accepted_bookings = bookings.filter(status='accepted')
    completed_bookings = bookings.filter(status='completed')
    
    context = {
        'bookings': bookings,
        'pending_bookings': pending_bookings,
        'accepted_bookings': accepted_bookings,
        'completed_bookings': completed_bookings,
        'pending_count': pending_bookings.count(),
        'accepted_count': accepted_bookings.count(),
        'completed_count': completed_bookings.count(),
    }
    return render(request, 'bookings/list.html', context)


@login_required
def booking_detail(request, booking_id):
    """Detalle de una reserva"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que el usuario tenga acceso
    if booking.customer != request.user and booking.provider != request.user:
        messages.error(request, 'No tienes acceso a esta reserva')
        return redirect('bookings_list')
    
    context = {
        'booking': booking,
    }
    return render(request, 'bookings/detail.html', context)


@login_required
def booking_create(request):
    """Crear una nueva reserva con validaciones mejoradas"""
    if request.method != 'POST':
        return redirect('services_list')
    
    # Verificar que sea cliente
    if request.user.profile.role != 'customer':
        messages.error(request, 'Solo los clientes pueden hacer reservas')
        return redirect('services_list')
    
    service_id = request.POST.get('service_id')
    provider_id = request.POST.get('provider_id')
    location_id = request.POST.get('location_id')
    selected_date = request.POST.get('selected_date')
    selected_time = request.POST.get('selected_time')
    notes = request.POST.get('notes', '')
    
    # Validar datos
    service = get_object_or_404(Service, id=service_id)
    provider = get_object_or_404(User, id=provider_id)
    location = get_object_or_404(Location, id=location_id, customer=request.user)
    
    # Combinar fecha y hora
    try:
        scheduled_datetime = datetime.strptime(
            f"{selected_date} {selected_time}", 
            "%Y-%m-%d %H:%M"
        )
        scheduled_datetime = timezone.make_aware(scheduled_datetime)
    except ValueError:
        messages.error(request, 'Fecha u hora inválida')
        return redirect('service_detail', service_id=service.id)
    
    # Validar que sea al menos 1 hora en el futuro
    now = timezone.now()
    if scheduled_datetime < now + timedelta(hours=1):
        messages.error(request, 'La reserva debe ser al menos 1 hora en el futuro')
        return redirect('service_detail', service_id=service.id)
    
    # Verificar que el horario esté disponible
    available_slots = get_available_time_slots(
        provider, 
        scheduled_datetime.date(), 
        service.duration_minutes
    )
    
    selected_time_obj = scheduled_datetime.time()
    if not any(slot['time'] == selected_time_obj for slot in available_slots):
        messages.error(request, 'El horario seleccionado ya no está disponible')
        return redirect('service_detail', service_id=service.id)
    
    # Verificar matching de zonas
    if location.zone not in provider.provider_profile.coverage_zones.all():
        messages.error(request, 'El proveedor no cubre la zona de tu ubicación')
        return redirect('service_detail', service_id=service.id)
    
    # Crear lista de servicios
    service_list = [{
        'service_id': service.id,
        'name': service.name,
        'price': float(service.base_price)
    }]
    
    total_cost = float(service.base_price)
    
    # Agregar costo de traslado
    if hasattr(provider, 'provider_profile'):
        total_cost += float(provider.provider_profile.avg_travel_cost)
    
    # Crear reserva
    booking = Booking.objects.create(
        customer=request.user,
        provider=provider,
        service_list=service_list,
        total_cost=total_cost,
        location=location,
        scheduled_time=scheduled_datetime,
        notes=notes,
        status='pending',
        payment_status='pending'
    )
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action='Reserva creada',
        metadata={'booking_id': str(booking.id)}
    )
    
    messages.success(request, '¡Reserva creada exitosamente! El proveedor la revisará pronto.')
    return redirect('booking_detail', booking_id=booking.id)


@login_required
def booking_accept(request, booking_id):
    """Aceptar una reserva (solo proveedor)"""
    if request.method != 'POST':
        return redirect('bookings_list')
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el proveedor
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    if booking.status != 'pending':
        messages.error(request, 'Esta reserva ya no está pendiente')
        return redirect('booking_detail', booking_id=booking.id)
    
    booking.status = 'accepted'
    booking.save()
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action='Reserva aceptada',
        metadata={'booking_id': str(booking.id)}
    )
    
    messages.success(request, 'Reserva aceptada. El cliente ha sido notificado.')
    return redirect('booking_detail', booking_id=booking.id)


@login_required
def booking_reject(request, booking_id):
    """Rechazar una reserva (solo proveedor)"""
    if request.method != 'POST':
        return redirect('bookings_list')
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el proveedor
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    if booking.status != 'pending':
        messages.error(request, 'Esta reserva ya no está pendiente')
        return redirect('booking_detail', booking_id=booking.id)
    
    booking.status = 'cancelled'
    booking.save()
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action='Reserva rechazada',
        metadata={'booking_id': str(booking.id)}
    )
    
    messages.info(request, 'Reserva rechazada.')
    return redirect('bookings_list')



@login_required
def booking_complete(request, booking_id):
    """Completar una reserva CON VALIDACIONES"""
    if request.method != 'POST':
        return redirect('bookings_list')
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el proveedor
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    # VALIDACIÓN 1: Debe estar aceptada
    if booking.status != 'accepted':
        messages.error(request, 'Solo puedes completar reservas aceptadas')
        return redirect('booking_detail', booking_id=booking.id)
    
    # VALIDACIÓN 2: Debe estar pagada
    if booking.payment_status != 'paid':
        messages.error(request, 'No puedes completar una reserva que no ha sido pagada')
        return redirect('booking_detail', booking_id=booking.id)
    
    # VALIDACIÓN 3: La fecha/hora debe haber pasado o estar cerca
    now = timezone.now()
    scheduled = booking.scheduled_time
    time_diff = (now - scheduled).total_seconds() / 60  # diferencia en minutos
    
    # Permitir completar 30 minutos antes de la hora programada
    if time_diff < -30:
        hours_left = abs(time_diff) / 60
        messages.error(
            request, 
            f'No puedes completar esta reserva aún. '
            f'Faltan {hours_left:.1f} horas para la hora programada.'
        )
        return redirect('booking_detail', booking_id=booking.id)
    
    # TODO OK - Completar
    booking.status = 'completed'
    booking.save()
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action='Reserva completada',
        metadata={'booking_id': str(booking.id)}
    )
    
    messages.success(request, 'Reserva marcada como completada. ¡Buen trabajo!')
    return redirect('booking_detail', booking_id=booking.id)


# ============================================================================
# LOCATION VIEWS
# ============================================================================

@login_required
def location_create(request):
    """Crear una nueva ubicación con mapa"""
    zones = Zone.objects.filter(active=True).order_by('name')
    
    if request.method == 'POST':
        label = request.POST.get('label')
        zone_id = request.POST.get('zone')
        address = request.POST.get('address')
        reference = request.POST.get('reference', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        # Validar coordenadas
        if not latitude or not longitude:
            messages.error(request, 'Debes seleccionar una ubicación en el mapa')
            return render(request, 'locations/create.html', {'zones': zones})
        
        # Validar zona
        zone = get_object_or_404(Zone, id=zone_id, active=True)
        
        location = Location.objects.create(
            customer=request.user,
            label=label,
            zone=zone,
            address=address,
            reference=reference,
            latitude=latitude,
            longitude=longitude
        )
        
        messages.success(request, 'Ubicación agregada exitosamente')
        
        # Redirigir a next o dashboard
        next_url = request.GET.get('next', 'dashboard')
        return redirect(next_url)
    
    context = {
        'zones': zones,
    }
    return render(request, 'locations/create.html', context)


@login_required
def location_delete(request, location_id):
    """Eliminar una ubicación"""
    location = get_object_or_404(Location, id=location_id, customer=request.user)
    location.delete()
    
    messages.success(request, 'Ubicación eliminada')
    return redirect('dashboard')


# ============================================================================
# REVIEW VIEWS
# ============================================================================

@login_required
def review_create(request, booking_id):
    """Crear una reseña"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el cliente
    if booking.customer != request.user:
        messages.error(request, 'No puedes reseñar esta reserva')
        return redirect('bookings_list')
    
    # Verificar que esté completada
    if booking.status != 'completed':
        messages.error(request, 'Solo puedes reseñar reservas completadas')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Verificar que no tenga reseña ya
    if hasattr(booking, 'review'):
        messages.error(request, 'Ya has reseñado esta reserva')
        return redirect('booking_detail', booking_id=booking.id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        Review.objects.create(
            booking=booking,
            customer=request.user,
            rating=int(rating),
            comment=comment
        )
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Reseña creada',
            metadata={'booking_id': str(booking.id), 'rating': rating}
        )
        
        messages.success(request, '¡Gracias por tu reseña!')
        return redirect('booking_detail', booking_id=booking.id)
    
    context = {
        'booking': booking,
    }
    return render(request, 'reviews/create.html', context)


# ============================================================================
# PAYMENT VIEWS
# ============================================================================

@login_required
def payment_process(request, booking_id):
    """Página de selección de método de pago"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el cliente
    if booking.customer != request.user:
        messages.error(request, 'No tienes acceso a esta reserva')
        return redirect('bookings_list')
    
    # Verificar que no esté pagada
    if booking.payment_status == 'paid':
        messages.info(request, 'Esta reserva ya está pagada')
        return redirect('booking_detail', booking_id=booking.id)
    
    context = {
        'booking': booking,
    }
    return render(request, 'payments/process.html', context)


@login_required
def payphone_create(request):
    """Crear pago con PayPhone - placeholder"""
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        # TODO: Integrar con PayPhone API real
        # Por ahora, simulamos el proceso
        
        booking.payment_method = 'payphone'
        booking.payment_status = 'pending'
        booking.save()
        
        messages.info(request, 'Redirigiendo a PayPhone... (Por implementar)')
        return redirect('booking_detail', booking_id=booking.id)
    
    return redirect('bookings_list')


@login_required
def bank_transfer(request):
    """Registrar transferencia bancaria"""
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        reference = request.POST.get('reference')
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        booking.payment_method = 'bank_transfer'
        booking.payment_status = 'pending'
        booking.notes = f"{booking.notes}\n\nReferencia de transferencia: {reference}"
        booking.save()
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Transferencia bancaria registrada',
            metadata={'booking_id': str(booking.id), 'reference': reference}
        )
        
        messages.success(request, 'Transferencia registrada. Será verificada por el equipo.')
        return redirect('booking_detail', booking_id=booking.id)
    
    return redirect('bookings_list')


@login_required
def payment_cash(request):
    """Registrar pago en efectivo acordado"""
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        booking.payment_method = 'cash'
        booking.payment_status = 'pending'
        booking.save()
        
        messages.success(request, 'Pago en efectivo acordado con el proveedor')
        return redirect('booking_detail', booking_id=booking.id)
    
    return redirect('bookings_list')


# ============================================================================
# SERVICE MANAGEMENT (PROVIDER)
# ============================================================================

@login_required
def service_create(request):
    """Crear nuevo servicio (solo proveedores)"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden crear servicios')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        base_price = request.POST.get('base_price')
        duration_minutes = request.POST.get('duration_minutes')
        image = request.FILES.get('image')
        available = request.POST.get('available') == 'on'  # ← AGREGAR ESTA LÍNEA
        
        service = Service.objects.create(
            provider=request.user,
            name=name,
            description=description,
            base_price=base_price,
            duration_minutes=duration_minutes,
            image=image,
            available=available  # ← AGREGAR ESTA LÍNEA
        )
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Servicio creado',
            metadata={'service_id': service.id, 'name': name}
        )
        
        messages.success(request, 'Servicio creado exitosamente')
        return redirect('dashboard')
    
    return render(request, 'services/create.html')


@login_required
def service_edit(request, service_id):
    """Editar servicio (solo proveedores)"""
    service = get_object_or_404(Service, id=service_id, provider=request.user)
    
    if request.method == 'POST':
        service.name = request.POST.get('name')
        service.description = request.POST.get('description')
        service.base_price = request.POST.get('base_price')
        service.duration_minutes = request.POST.get('duration_minutes')
        service.available = request.POST.get('available') == 'on'  # ← AGREGAR ESTA LÍNEA
        
        if request.FILES.get('image'):
            service.image = request.FILES.get('image')
        
        service.save()
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Servicio actualizado',
            metadata={'service_id': service.id, 'name': service.name}
        )
        
        messages.success(request, 'Servicio actualizado')
        return redirect('dashboard')
    
    context = {
        'service': service,
    }
    return render(request, 'services/edit.html', context)

@login_required
def service_delete(request, service_id):
    """Eliminar servicio (solo proveedores)"""
    service = get_object_or_404(Service, id=service_id, provider=request.user)
    
    if request.method == 'POST':
        service_name = service.name
        service.delete()
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Servicio eliminado',
            metadata={'service_name': service_name}
        )
        
        messages.success(request, 'Servicio eliminado')
        return redirect('dashboard')
    
    return redirect('dashboard')

def get_available_time_slots(provider, service_date, service_duration_minutes):
    """
    Obtiene los horarios disponibles para un proveedor en una fecha específica
    """
    # Obtener día de la semana (0=Lunes, 6=Domingo)
    day_of_week = service_date.weekday()
    
    # Verificar si el proveedor está inactivo ese día
    unavailabilities = ProviderUnavailability.objects.filter(
        provider=provider,
        start_date__lte=service_date,
        end_date__gte=service_date
    )
    
    if unavailabilities.exists():
        return []  # Proveedor no disponible este día
    
    # Obtener horarios configurados para ese día
    schedules = ProviderSchedule.objects.filter(
        provider=provider,
        day_of_week=day_of_week,
        is_active=True
    )
    
    if not schedules.exists():
        return []  # No tiene horarios configurados para este día
    
    # Obtener reservas existentes para ese día
    existing_bookings = Booking.objects.filter(
        provider=provider,
        scheduled_time__date=service_date,
        status__in=['pending', 'accepted']
    )
    
    available_slots = []
    
    for schedule in schedules:
        # Crear slots de 30 minutos dentro del horario
        current_time = datetime.combine(service_date, schedule.start_time)
        end_time = datetime.combine(service_date, schedule.end_time)
        
        while current_time + timedelta(minutes=service_duration_minutes) <= end_time:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=service_duration_minutes)
            
            # Verificar si este slot está ocupado
            is_occupied = False
            for booking in existing_bookings:
                booking_start = booking.scheduled_time
                booking_end = booking_start + timedelta(minutes=60)  # Estimado
                
                # Verificar solapamiento
                if (slot_start < booking_end and slot_end > booking_start):
                    is_occupied = True
                    break
            
            if not is_occupied:
                # Verificar que sea al menos 1 hora en el futuro
                now = timezone.now()
                if timezone.make_aware(slot_start) > now + timedelta(hours=1):
                    available_slots.append({
                        'time': slot_start.time(),
                        'display': slot_start.strftime('%H:%M')
                    })
            
            # Avanzar 30 minutos
            current_time += timedelta(minutes=30)
    
    return available_slots

@login_required
def booking_create_step1(request, service_id):
    """Paso 1: Seleccionar fecha y ver horarios disponibles"""
    service = get_object_or_404(Service, id=service_id)
    provider = service.provider
    
    # Obtener ubicaciones del usuario con zona
    user_locations = Location.objects.filter(customer=request.user).select_related('zone')
    
    # Verificar que el proveedor cubra alguna zona del usuario
    if user_locations.exists():
        user_zones = set(loc.zone_id for loc in user_locations if loc.zone)
        provider_zones = set(provider.provider_profile.coverage_zones.values_list('id', flat=True))
        
        if not user_zones.intersection(provider_zones):
            messages.warning(
                request, 
                'Este proveedor no cubre ninguna de tus ubicaciones. '
                'Agrega una ubicación en una zona que el proveedor cubra.'
            )
    
    selected_date = request.GET.get('date')
    available_slots = []
    
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            
            # Validar que sea hoy o futuro
            if date_obj < timezone.now().date():
                messages.error(request, 'No puedes seleccionar una fecha pasada')
            else:
                available_slots = get_available_time_slots(
                    provider, 
                    date_obj, 
                    service.duration_minutes
                )
                
                if not available_slots:
                    messages.info(request, 'No hay horarios disponibles para esta fecha')
        except ValueError:
            messages.error(request, 'Fecha inválida')
    
    # Obtener próximos 30 días disponibles
    available_dates = []
    current_date = timezone.now().date()
    
    for i in range(30):
        check_date = current_date + timedelta(days=i)
        day_of_week = check_date.weekday()
        
        # Verificar si tiene horarios ese día
        has_schedule = ProviderSchedule.objects.filter(
            provider=provider,
            day_of_week=day_of_week,
            is_active=True
        ).exists()
        
        # Verificar si NO está inactivo
        is_available = not ProviderUnavailability.objects.filter(
            provider=provider,
            start_date__lte=check_date,
            end_date__gte=check_date
        ).exists()
        
        if has_schedule and is_available:
            available_dates.append(check_date)
    
    context = {
        'service': service,
        'provider': provider,
        'user_locations': user_locations,
        'selected_date': selected_date,
        'available_slots': available_slots,
        'available_dates': available_dates,
        'min_date': timezone.now().date(),
    }
    return render(request, 'bookings/create_step1.html', context)

@login_required
def provider_schedule_manage(request):
    """Gestión de horarios del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar horarios')
        return redirect('dashboard')
    
    schedules = ProviderSchedule.objects.filter(
        provider=request.user
    ).order_by('day_of_week', 'start_time')
    
    # Agrupar por día
    schedules_by_day = {}
    for schedule in schedules:
        day = schedule.get_day_of_week_display()
        if day not in schedules_by_day:
            schedules_by_day[day] = []
        schedules_by_day[day].append(schedule)
    
    context = {
        'schedules': schedules,
        'schedules_by_day': schedules_by_day,
    }
    return render(request, 'providers/schedule_manage.html', context)

@login_required
def provider_schedule_create(request):
    """Crear horario del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar horarios')
        return redirect('dashboard')
    
    if request.method == 'POST':
        day_of_week = request.POST.get('day_of_week')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        
        # Validar que start < end
        if start_time >= end_time:
            messages.error(request, 'La hora de inicio debe ser menor que la hora de fin')
            return redirect('provider_schedule_manage')
        
        # Verificar si ya existe un horario similar
        existing = ProviderSchedule.objects.filter(
            provider=request.user,
            day_of_week=day_of_week,
            start_time=start_time
        ).exists()
        
        if existing:
            messages.error(request, 'Ya tienes un horario para este día y hora')
            return redirect('provider_schedule_manage')
        
        # Crear
        ProviderSchedule.objects.create(
            provider=request.user,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_active=True
        )
        
        messages.success(request, 'Horario agregado exitosamente')
        return redirect('provider_schedule_manage')
    
    return render(request, 'providers/schedule_create.html')

@login_required
def provider_schedule_delete(request, schedule_id):
    """Eliminar horario"""
    schedule = get_object_or_404(ProviderSchedule, id=schedule_id, provider=request.user)
    
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, 'Horario eliminado')
        return redirect('provider_schedule_manage')
    
    return redirect('provider_schedule_manage')


@login_required
def provider_unavailability_manage(request):
    """Gestión de días de inactividad/vacaciones"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar inactividades')
        return redirect('dashboard')
    
    unavailabilities = ProviderUnavailability.objects.filter(
        provider=request.user
    ).order_by('-start_date')
    
    context = {
        'unavailabilities': unavailabilities,
    }
    return render(request, 'providers/unavailability_manage.html', context)


@login_required
def provider_unavailability_create(request):
    """Crear período de inactividad"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar inactividades')
        return redirect('dashboard')
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason', '')
        
        # Validar fechas
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if end < start:
            messages.error(request, 'La fecha de fin debe ser mayor o igual a la fecha de inicio')
            return redirect('provider_unavailability_manage')
        
        if start < timezone.now().date():
            messages.error(request, 'No puedes crear inactividades para fechas pasadas')
            return redirect('provider_unavailability_manage')
        
        # Crear
        ProviderUnavailability.objects.create(
            provider=request.user,
            start_date=start,
            end_date=end,
            reason=reason
        )
        
        messages.success(request, 'Período de inactividad registrado')
        return redirect('provider_unavailability_manage')
    
    context = {
        'min_date': timezone.now().date(),
    }
    return render(request, 'providers/unavailability_create.html', context)


@login_required
def provider_unavailability_delete(request, unavailability_id):
    """Eliminar período de inactividad"""
    unavailability = get_object_or_404(
        ProviderUnavailability, 
        id=unavailability_id, 
        provider=request.user
    )
    
    if request.method == 'POST':
        unavailability.delete()
        messages.success(request, 'Período de inactividad eliminado')
        return redirect('provider_unavailability_manage')
    
    return redirect('provider_unavailability_manage')


@login_required
def provider_toggle_active(request):
    """Activar/Desactivar proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden hacer esto')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    profile = request.user.provider_profile
    profile.is_active = not profile.is_active
    profile.save()
    
    status = 'activado' if profile.is_active else 'desactivado'
    messages.success(request, f'Tu perfil ha sido {status}')
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action=f'Proveedor {status}',
        metadata={'is_active': profile.is_active}
    )
    
    return redirect('dashboard')