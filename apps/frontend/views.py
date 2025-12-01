from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from apps.core.email_utils import send_mail
from django.db.models import Q, Avg, Count, Sum, F
from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.password_validation import validate_password

from django.http import HttpResponseRedirect
from allauth.socialaccount.providers.google.views import oauth2_login
from uuid import UUID

import requests
import logging

from django.db import transaction

from apps.core.models import (
    Profile, Category, Service, ProviderProfile, 
    Booking, Location, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability,
    PaymentMethod, BankAccount, PaymentProof,
    ProviderZoneCost, SystemConfig, Notification, Payment,
    WithdrawalRequest, ProviderBankAccount, Bank,
    EmailVerificationToken, City, PasswordResetToken,
    ProviderLocation
)

from apps.frontend.forms import (
    ProviderLocationForm, ProviderProfileServiceModeForm
)
from apps.legal.models import LegalDocument, LegalAcceptance
from apps.legal.views import get_client_ip, get_user_agent

from core.image_upload import (
    upload_profile_photo, replace_image, 
    upload_service_image, upload_payment_proof,
    delete_image, upload_image, validate_image
)

from core.tasks import (
    send_payment_confirmed_to_customer_task,
    send_payment_received_to_provider_task
)

from core.email_verification import send_verification_email, send_welcome_email

from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

def get_active_categories():
    """Obtiene todas las categorías ordenadas por nombre"""
    return Category.objects.all().order_by('name')

def get_current_city(request):
    """Obtiene la ciudad actual del usuario o de sesión"""
    # 1. De perfil si está autenticado
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.current_city:
            logger.info(f"get_current_city - Desde perfil usuario: {request.user.profile.current_city.name}")
            return request.user.profile.current_city
    
    # 2. De sesión
    city_id = request.session.get('current_city_id')
    if city_id:
        try:
            city = City.objects.get(id=city_id, active=True)
            logger.info(f"get_current_city - Desde sesión: {city.name} (ID: {city_id})")
            return city
        except City.DoesNotExist:
            logger.warning(f"get_current_city - Ciudad ID {city_id} no existe en DB")
            pass
    
    # 3. Default: primera ciudad activa
    default_city = City.objects.filter(active=True).order_by('display_order').first()
    if default_city:
        logger.info(f"get_current_city - Default (primera ciudad): {default_city.name}")
    else:
        logger.error("get_current_city - ⚠️ NO HAY CIUDADES ACTIVAS EN EL SISTEMA")
    return default_city


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
    
    context = {
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'recent_bookings': recent_bookings,
        'pending_reviews': pending_reviews,
        'locations': locations,
        'total_locations': total_locations,
        'categories': get_active_categories(),
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
    
    # NUEVO: Calcular saldo activo disponible para retirar
    active_balance = get_active_balance(request.user)
    
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
    
    # ✅ NUEVO: Verificar modalidad y ubicaciones
    from apps.core.models import ProviderLocation
    # Verificar que service_mode tenga un valor válido (no None, no '', no blank)
    has_service_mode = provider_profile.service_mode in ['home', 'local', 'both']
    has_base_location = ProviderLocation.objects.filter(provider=request.user, location_type='base').exists()
    has_local_locations = ProviderLocation.objects.filter(provider=request.user, location_type='local').exists()
    
    context = {
        'provider_profile': provider_profile,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'total_earnings': total_earnings,
        'active_balance': active_balance,  # NUEVO
        'recent_bookings': recent_bookings,
        'services': services,
        'recent_reviews': recent_reviews,
        'rating_avg': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'has_service_mode': has_service_mode,  # ✅ NUEVO
        'has_base_location': has_base_location,  # ✅ NUEVO
        'has_local_locations': has_local_locations,  # ✅ NUEVO
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
    """Detalle de una reserva con lógica de contacto y código de finalización"""
    try:
        # 1. Intenta validar si la cadena tiene formato UUID.
        UUID(booking_id)
        
        # 2. Si la validación pasa, intentamos buscar el objeto por el campo 'id' (UUID).
        booking = get_object_or_404(Booking, id=booking_id)

    except ValueError:
        # 3. Si se lanzó un ValueError (el identificador no era un UUID), 
        # intentamos buscar por el campo 'slug' (string).
        booking = get_object_or_404(Booking, slug=booking_id)
    
    # Verificar que el usuario tenga acceso
    if booking.customer != request.user and booking.provider != request.user:
        messages.error(request, 'No tienes acceso a esta reserva')
        return redirect('bookings_list')
    
    # LÓGICA DE CONTACTO: Determinar si puede ver WhatsApp/teléfono
    can_contact = False
    contact_message = None
    
    if request.user.profile.role == 'customer':
        # Cliente puede contactar si:
        # 1. Ha pagado
        # 2. Faltan 2 horas o menos para la cita
        if booking.payment_status == 'paid':
            now = timezone.now()
            time_until_booking = booking.scheduled_time - now
            hours_until = time_until_booking.total_seconds() / 3600
            
            if hours_until <= 2:
                can_contact = True
                
                # NUEVO: Generar código de finalización si no existe
                if not booking.completion_code:
                    booking.generate_completion_code()
                    
            else:
                # Calcular horas restantes para mostrar
                hours_remaining = int(hours_until)
                contact_message = f'El contacto estará disponible 2 horas antes de tu cita (faltan {hours_remaining} horas) y luego del pago exitoso.'
        else:
            contact_message = 'Completa el pago para acceder a los datos de contacto'
    
    elif request.user.profile.role == 'provider':
        # Proveedor puede contactar si:
        # 1. Faltan 2 horas o menos para la cita
        # 2. O ya pasó la hora de la cita (para seguimiento)
        now = timezone.now()
        time_until_booking = booking.scheduled_time - now
        hours_until = time_until_booking.total_seconds() / 3600
        
        if booking.payment_status == 'paid' and hours_until <= 2:
            can_contact = True
        else:
            hours_remaining = int(hours_until)
            contact_message = f'El contacto estará disponible 2 horas antes de la cita (faltan {hours_remaining} horas) y luego del pago exitoso.'
    
    # Determinar si mostrar código de finalización al cliente
    show_completion_code = False
    if request.user.profile.role == 'customer':
        show_completion_code = booking.should_show_completion_code()
    
    context = {
        'booking': booking,
        'can_contact': can_contact,
        'contact_message': contact_message,
        'show_completion_code': show_completion_code,  # NUEVO
        'booking_location': booking.location,
        'booking_location_lat': float(booking.location.latitude) if booking.location else None,
        'booking_location_lng': float(booking.location.longitude) if booking.location else None,
    }
    return render(request, 'bookings/detail.html', context)

def decimal_to_json(value):
    """Convierte Decimal a string para JSON"""
    return str(value) if isinstance(value, Decimal) else value

@login_required
def booking_create(request):
    """Crear una nueva reserva con validaciones mejoradas por zona"""
    
    if request.method != 'POST':
        return redirect('services_list')
    
    if request.user.profile.role != 'customer':
        messages.error(request, 'Solo los clientes pueden hacer reservas')
        return redirect('services_list')
    
    service_id = request.POST.get('service_id')
    provider_id = request.POST.get('provider_id')
    location_id = request.POST.get('location_id')
    service_mode = request.POST.get('service_mode', 'home')
    provider_location_id = request.POST.get('provider_location_id')
    selected_date = request.POST.get('selected_date')
    selected_time = request.POST.get('selected_time')
    notes = request.POST.get('notes', '')
    
    logger.info(f"📝 Intentando crear reserva: service_id={service_id}, provider_id={provider_id}")
    logger.info(f"   Modo: {service_mode}, location_id: {location_id}, provider_location_id: {provider_location_id}")
    
    service = get_object_or_404(Service, id=service_id)
    provider = get_object_or_404(User, id=provider_id)
    
    # ✅ CORRECCIÓN: Location del cliente solo es obligatoria en modo 'home'
    location = None
    if service_mode == 'home':
        if not location_id:
            messages.error(request, 'Debe seleccionar una ubicación para servicio a domicilio')
            return redirect('service_detail', service_code=service.service_code)
        location = get_object_or_404(Location, id=location_id, customer=request.user)
    
    # NUEVO: Obtener ubicación del proveedor si se especificó
    provider_location = None
    if provider_location_id:
        from apps.core.models import ProviderLocation
        try:
            provider_location = ProviderLocation.objects.get(
                id=provider_location_id,
                provider=provider
            )
            if provider_location.location_type == 'local' and not provider_location.is_verified:
                messages.error(request, 'Ubicación no verificada')
                return redirect('service_detail', service_code=service.service_code)
        except ProviderLocation.DoesNotExist:
            messages.error(request, 'Ubicación inválida')
            return redirect('service_detail', service_code=service.service_code)
    
    # ✅ VALIDACIÓN DE ZONA: Solo aplica para modo 'home'
    if service_mode == 'home':
        if not location.zone:
            messages.error(request, 'La ubicación seleccionada no tiene zona asignada')
            return redirect('service_detail', service_code=service.service_code)
        
        provider_covers_zone = provider.provider_profile.coverage_zones.filter(
            id=location.zone_id
        ).exists()
        
        if not provider_covers_zone:
            messages.error(
                request,
                f'El proveedor no cubre la zona {location.zone.name}.'
            )
            return redirect('service_detail', service_code=service.service_code)
    
    elif service_mode == 'local':
        # En modo local, validar que se haya seleccionado un provider_location
        if not provider_location:
            messages.error(request, 'Debe seleccionar un local del proveedor')
            return redirect('service_detail', service_code=service.service_code)
    
    # Combinar fecha y hora
    try:
        scheduled_datetime = datetime.strptime(
            f"{selected_date} {selected_time}", 
            "%Y-%m-%d %H:%M"
        )
        scheduled_datetime = timezone.make_aware(scheduled_datetime)
        logger.info(f"✅ Fecha/hora parseada: {scheduled_datetime}")
    except ValueError as e:
        logger.error(f"❌ Error parseando fecha: {e}")
        messages.error(request, 'Fecha u hora inválida')
        return redirect('service_detail', service_code=service.service_code)
    
    # Validar tiempo mínimo
    min_hours = SystemConfig.get_config('min_booking_hours', 1)
    now = timezone.now()
    if scheduled_datetime < now + timedelta(hours=min_hours):
        messages.error(
            request,
            f'La reserva debe ser al menos {min_hours} hora(s) en el futuro'
        )
        return redirect('service_detail', service_code=service.service_code)
    
    # Validar que NO tenga otra reserva del MISMO SERVICIO ese DÍA
    logger.info(f"🔍 Buscando reservas duplicadas...")
    
    bookings_that_day = Booking.objects.filter(
        customer=request.user,
        provider=provider,
        scheduled_time__date=scheduled_datetime.date(),
        status__in=['pending', 'accepted'],
        payment_status__in=['pending', 'pending_validation', 'paid']
    ).values_list('id', 'service_list')
    
    for booking_id, service_list in bookings_that_day:
        if service_list and isinstance(service_list, list):
            for service_item in service_list:
                item_service_id = service_item.get('service_id')
                
                if int(item_service_id) == int(service_id):
                    error_msg = f'Ya tienes una reserva del servicio "{service.name}" para el {scheduled_datetime.strftime("%d/%m")}.'
                    logger.warning(f"❌ DUPLICADO DETECTADO: {error_msg}")
                    messages.error(request, error_msg)
                    return redirect('service_detail', service_code=service.service_code)
    
    logger.info(f"✅ No hay duplicados. Continuando...")
    
    # Verificar horarios disponibles
    available_slots = get_available_time_slots(
        provider, 
        scheduled_datetime.date(), 
        service.duration_minutes,
        service_id
    )
    
    selected_time_obj = scheduled_datetime.time()
    if not any(slot['time'] == selected_time_obj for slot in available_slots):
        messages.error(request, 'El horario seleccionado ya no está disponible')
        return redirect('service_detail', service_code=service.service_code)
    
    # Crear lista de servicios y cálculos
    service_list = [{
        'service_id': service.id,
        'name': service.name,
        'price': decimal_to_json(service.base_price)
    }]
    
    sub_total_cost = Decimal(service.base_price)
    
    # ✅ Costo de traslado solo aplica en modo 'home'
    travel_cost = Decimal('0.00')
    if service_mode == 'home' and location:
        zone_cost = ProviderZoneCost.objects.filter(    
            provider=provider,
            zone=location.zone
        ).first()
        
        if zone_cost:
            travel_cost = Decimal(zone_cost.travel_cost)
        else:
            travel_cost = Decimal(SystemConfig.get_config('default_travel_cost', 2.50))
    
    service_fee = Decimal(settings.TAXES_ENDUSER_SERVICE_COMMISSION)
    iva = Decimal(settings.TAXES_IVA)
    tax = sub_total_cost * iva + service_fee * iva

    total_cost = sub_total_cost + travel_cost + tax
    
    # Crear reserva CON provider_location
    booking = Booking.objects.create(
        customer=request.user,
        provider=provider,
        service_list=service_list,
        sub_total_cost=sub_total_cost,
        service=service_fee,
        tax=tax,
        total_cost=total_cost,
        travel_cost=travel_cost,
        location=location,
        provider_location=provider_location,  # AGREGAR ESTO
        scheduled_time=scheduled_datetime,
        notes=notes,
        status='pending',
        payment_status='pending'
    )
    
    logger.info(f"✅ Reserva creada exitosamente: {booking.id}")

    # Notificar al proveedor
    Notification.objects.create(
        user=provider,
        notification_type='booking_created',
        title='📋 Nueva Reserva Recibida',
        message=f'{request.user.get_full_name() or request.user.username} ha creado una nueva reserva para {scheduled_datetime.strftime("%d/%m/%Y %H:%M")}. Monto: ${total_cost}',
        booking=booking,
        action_url=f'/bookings/{booking.id}/'
    )

    try:
        from core.tasks import send_new_booking_to_provider_task
        send_new_booking_to_provider_task.delay(booking_id=str(booking.id))
    except Exception as e:
        logger.error(f"Error enviando email al proveedor: {e}")
    
    AuditLog.objects.create(
        user=request.user,
        action='Reserva creada',
        metadata={
            'booking_id': str(booking.id),
            'service_mode': service_mode,
            'zone': location.zone.name if location and location.zone else None,
            'provider_location': provider_location.label if provider_location else None,
            'travel_cost': str(travel_cost)
        }
    )
    
    messages.success(
        request,
        '¡Reserva creada exitosamente! El proveedor la revisará pronto.'
    )
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

    # ============================================
    # Crear notificación para cliente
    # ============================================
    Notification.objects.create(
        user=booking.customer,
        notification_type='booking_accepted',
        title='✅ Reserva Aceptada',
        message=f'{booking.provider.get_full_name() or booking.provider.username} ha aceptado tu reserva para el {booking.scheduled_time.strftime("%d/%m/%Y %H:%M")}. El siguiente paso es completar el pago.',
        booking=booking,
        action_url=f'/bookings/{booking.id}/'
    )

    # Enviar email de forma asincrónica
    try:
        from core.tasks import send_booking_accepted_to_customer_task
        send_booking_accepted_to_customer_task.delay(booking_id=str(booking.id))
    except Exception as e:
        logger.error(f"Error enviando email al cliente: {e}")
    
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
    if request.method != 'POST':
        return redirect('bookings_list')
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    is_provider = booking.provider == request.user
    is_customer = booking.customer == request.user
    
    if not (is_provider or is_customer):
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    if booking.status != 'accepted':
        messages.error(request, 'Solo puedes completar reservas aceptadas')
        return redirect('booking_detail', booking_id=booking.id)
    
    if booking.payment_status != 'paid':
        messages.error(request, 'No puedes completar una reserva que no ha sido pagada')
        return redirect('booking_detail', booking_id=booking.id)
    
    now = timezone.now()
    scheduled = booking.scheduled_time
    time_diff = (now - scheduled).total_seconds() / 60
    
    if time_diff < -30:
        hours_left = abs(time_diff) / 60
        messages.error(request, f'No puedes completar esta reserva aún. Faltan {hours_left:.1f} horas para la hora programada.')
        return redirect('booking_detail', booking_id=booking.id)
    

    with transaction.atomic():
        if is_provider:
            booking.provider_completed_at = timezone.now()
            messages.info(request, '✅ Marcada como completada por tu parte. Esperando confirmación del cliente.')
        elif is_customer:
            booking.customer_completed_at = timezone.now()
            messages.info(request, '✅ Marcada como completada por tu parte. Esperando confirmación del proveedor.')
        
        if booking.provider_completed_at and booking.customer_completed_at:
            booking.status = 'completed'
            messages.success(request, '✅ ¡Reserva completada exitosamente! Ambas partes han confirmado. El dinero ahora estará disponible para retirar.')
            
            Notification.objects.create(
                user=booking.customer,
                notification_type='booking_completed',
                title='✅ Reserva Completada',
                message=f'La reserva con {booking.provider.get_full_name()} ha sido completada por ambas partes.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='booking_completed',
                title='✅ Reserva Completada',
                message=f'La reserva con {booking.customer.get_full_name()} ha sido completada por ambas partes.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
        
        booking.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='Reserva marcada como completada',
            metadata={
                'booking_id': str(booking.id),
                'completed_by': 'provider' if is_provider else 'customer',
                'provider_confirmed': booking.provider_completed_at is not None,
                'customer_confirmed': booking.customer_completed_at is not None,
            }
        )
    
    return redirect('booking_detail', booking_id=booking.id)


# ============================================================================
# LOCATION VIEWS
# ============================================================================

@login_required
def location_create(request):
    """Crear una nueva ubicación con mapa"""
    # NUEVO: Obtener ciudad actual
    current_city = get_current_city(request)
    
    # NUEVO: Obtener zonas de la ciudad actual
    zones = Zone.objects.filter(
        active=True,
        city=current_city
    ).order_by('name') if current_city else Zone.objects.none()
    
    if request.method == 'POST':
        label = request.POST.get('label')
        zone_id = request.POST.get('zone')
        address = request.POST.get('address')
        reference = request.POST.get('reference', '')
        recipient_name = request.POST.get('recipient_name', '')  # NUEVO
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        # Validar coordenadas
        if not latitude or not longitude:
            messages.error(request, 'Debes seleccionar una ubicación en el mapa')
            return render(request, 'locations/create.html', {
                'zones': zones,
                'current_city': current_city,
            })
        
        # Validar zona - ACTUALIZAR para validar por city
        zone = get_object_or_404(Zone, id=zone_id, active=True, city=current_city)
        
        # NUEVO: Auto-asignar city desde zone
        location = Location.objects.create(
            customer=request.user,
            label=label,
            zone=zone,
            city=zone.city,
            address=address,
            reference=reference,
            recipient_name=recipient_name,  # NUEVO
            latitude=latitude,
            longitude=longitude
        )
        
        messages.success(request, 'Ubicación agregada exitosamente')
        
        # Redirigir a next o dashboard
        next_url = request.GET.get('next', 'dashboard')
        return redirect(next_url)
    
    context = {
        'zones': zones,
        'current_city': current_city,
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
        available = request.POST.get('available') == 'on'
        
        try:
            # Subir imagen del servicio
            image_url = upload_service_image(
                file=image,
                provider_id=request.user.id
            )
            
            # Crear servicio con la URL
            service = Service.objects.create(
                provider=request.user,
                name=name,
                description=description,
                base_price=base_price,
                duration_minutes=duration_minutes,
                image=image_url,  # URL de la imagen
                available=available
            )
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Servicio creado',
                metadata={'service_id': service.id, 'name': name}
            )

            # ============================================
            # CAMBIO #3: Verificar si es el primer servicio
            # ============================================
            provider_profile = request.user.provider_profile
            service_count = Service.objects.filter(provider=request.user).count()
            
            # Si es el primer servicio, cambiar estado a 'pending' y notificar admins
            if service_count == 1:
                provider_profile.status = 'pending'
                provider_profile.save()
                
                # Obtener todos los administradores
                admin_users = User.objects.filter(is_staff=True, is_active=True)
                admin_emails = [admin.email for admin in admin_users if admin.email]
                
                # Enviar notificación asincrónica
                if admin_emails:
                    try:
                        from core.tasks import send_provider_approval_notification_task
                        send_provider_approval_notification_task.delay(
                            provider_id=request.user.id,
                            admin_emails=admin_emails
                        )
                    except Exception as e:
                        logger.error(f"Error enviando notificación a admins: {e}")
                
                # Mostrar mensaje especial al proveedor
                messages.success(
                    request,
                    f'✅ Servicio "{name}" creado exitosamente. '
                    f'Tu solicitud de aprobación ha sido enviada a nuestro equipo. '
                    f'Recibirás una notificación cuando tu perfil sea revisado.'
                )
            else:
                messages.success(request, 'Servicio creado exitosamente')

            return redirect('dashboard')
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al crear servicio: {str(e)}')

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
        
        # Si se subió nueva imagen
        if request.FILES.get('image'):
            try:
                # Reemplazar imagen anterior
                new_image_url = replace_image(
                    old_url=service.image,
                    new_file=request.FILES['image'],
                    folder='services',
                    user_id=request.user.id,
                    prefix='service'
                )
                service.image = new_image_url
            except Exception as e:
                messages.error(request, f'Error al actualizar imagen: {str(e)}')
                return render(request, 'services/edit.html', {'service': service})
        
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

        # Eliminar imagen asociada
        if service.image:
            delete_image(service.image)
        
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

def get_available_time_slots(provider, service_date, service_duration_minutes, service_id=None):
    """
    Obtiene los horarios disponibles para un proveedor en una fecha específica.
    CAMBIO #1 & #2: Solo bloquea horarios de reservas ACEPTADAS Y PAGADAS
    """
    from django.utils import timezone
    
    # Obtener día de la semana (0=Lunes, 6=Domingo)
    day_of_week = service_date.weekday()
    
    # Verificar si el proveedor está inactivo ese día
    unavailabilities = ProviderUnavailability.objects.filter(
        provider=provider,
        start_date__lte=service_date,
        end_date__gte=service_date
    )
    
    if unavailabilities.exists():
        return []
    
    # Obtener horarios configurados para ese día
    schedules = ProviderSchedule.objects.filter(
        provider=provider,
        day_of_week=day_of_week,
        is_active=True
    )
    
    if not schedules.exists():
        return []
    
    # CAMBIO #1: Solo contar reservas ACEPTADAS Y PAGADAS como bloqueadas
    existing_bookings = Booking.objects.filter(
        provider=provider,
        scheduled_time__date=service_date,
        status='accepted',           # ← CAMBIO: Solo aceptadas
        payment_status='paid'        # ← CAMBIO: Solo pagadas
    )
    
    available_slots = []
    
    for schedule in schedules:
        current_time = datetime.combine(service_date, schedule.start_time)
        end_time = datetime.combine(service_date, schedule.end_time)
        
        current_time = timezone.make_aware(current_time)
        end_time = timezone.make_aware(end_time)
        
        while current_time + timedelta(minutes=service_duration_minutes) <= end_time:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=service_duration_minutes)
            
            # Verificar si este slot está ocupado por reserva confirmada
            is_occupied = False
            for booking in existing_bookings:
                booking_start = booking.scheduled_time
                booking_end = booking_start + timedelta(minutes=60)
                
                if (slot_start < booking_end and slot_end > booking_start):
                    is_occupied = True
                    break
            
            if not is_occupied:
                now = timezone.now()
                if slot_start > now + timedelta(hours=1):
                    available_slots.append({
                        'time': slot_start.time(),
                        'display': slot_start.strftime('%H:%M')
                    })
            
            current_time += timedelta(minutes=30)
    
    return available_slots

# views.py - Reemplazar booking_create_step1 (líneas 2126-2202)

@login_required
def booking_create_step1(request, service_id):
    """Paso 1: Seleccionar fecha y ver horarios disponibles"""
    service = get_object_or_404(Service, id=service_id)
    provider = service.provider
    
    # Obtener modalidad y location_id de URL
    service_mode = request.GET.get('service_mode', 'home')
    provider_location_id = request.GET.get('location_id')
    
    # Si es modo local, obtener la ubicación del proveedor
    provider_location = None
    if service_mode == 'local' and provider_location_id:
        provider_location = get_object_or_404(
            ProviderLocation,
            id=provider_location_id,
            provider=provider,
            location_type='local',
            is_verified=True
        )
    
    # Obtener ubicaciones del usuario (solo para modo home)
    user_locations = []
    if service_mode == 'home':
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
        'service_mode': service_mode,
        'provider_location': provider_location,
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

@login_required
def provider_zone_costs_manage(request):
    """Gestión de costos de movilización por zona"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar costos por zona')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    # Obtener zonas de cobertura del proveedor
    coverage_zones = request.user.provider_profile.coverage_zones.all()
    
    # Obtener costos configurados
    zone_costs = ProviderZoneCost.objects.filter(
        provider=request.user
    ).select_related('zone')
    
    # Crear diccionario para fácil acceso
    costs_dict = {zc.zone_id: zc for zc in zone_costs}
    
    # Preparar datos para template
    zones_with_costs = []
    for zone in coverage_zones:
        zone_cost = costs_dict.get(zone.id)
        zones_with_costs.append({
            'zone': zone,
            'cost': zone_cost.travel_cost if zone_cost else None,
            'cost_id': zone_cost.id if zone_cost else None
        })
    
    # Obtener configuración máxima
    max_travel_cost = SystemConfig.get_config('max_travel_cost', 5)
    default_travel_cost = SystemConfig.get_config('default_travel_cost', 2.50)
    
    context = {
        'zones_with_costs': zones_with_costs,
        'max_travel_cost': max_travel_cost,
        'default_travel_cost': default_travel_cost,
    }
    return render(request, 'providers/zone_costs_manage.html', context)


@login_required
def provider_zone_cost_update(request):
    """Actualizar o crear costo por zona"""
    if request.method != 'POST':
        return redirect('provider_zone_costs_manage')
    
    if request.user.profile.role != 'provider':
        messages.error(request, 'No autorizado')
        return redirect('dashboard')
    
    zone_id = request.POST.get('zone_id')
    travel_cost = request.POST.get('travel_cost')
    
    try:
        zone = get_object_or_404(Zone, id=zone_id)
        cost = Decimal(travel_cost)
        
        # Validar máximo
        max_cost = SystemConfig.get_config('max_travel_cost', 5)
        if cost > max_cost:
            messages.error(request, f'El costo no puede superar ${max_cost} USD')
            return redirect('provider_zone_costs_manage')
        
        # Validar que la zona esté en su cobertura
        if not request.user.provider_profile.coverage_zones.filter(id=zone_id).exists():
            messages.error(request, 'Esta zona no está en tu cobertura')
            return redirect('provider_zone_costs_manage')
        
        # Crear o actualizar
        zone_cost, created = ProviderZoneCost.objects.update_or_create(
            provider=request.user,
            zone=zone,
            defaults={'travel_cost': cost}
        )
        
        action = 'configurado' if created else 'actualizado'
        messages.success(request, f'Costo de traslado {action} para {zone.name}')
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action=f'Costo de zona {action}',
            metadata={
                'zone': zone.name,
                'cost': str(cost)
            }
        )
        
    except Exception as e:
        messages.error(request, f'Error al guardar: {str(e)}')
    
    return redirect('provider_zone_costs_manage')


@login_required
def provider_zone_cost_delete(request, zone_id):
    """Eliminar configuración de costo por zona (volver a usar default)"""
    if request.method != 'POST':
        return redirect('provider_zone_costs_manage')
    
    zone_cost = get_object_or_404(
        ProviderZoneCost,
        provider=request.user,
        zone_id=zone_id
    )
    
    zone_name = zone_cost.zone.name
    zone_cost.delete()
    
    messages.success(request, f'Configuración eliminada para {zone_name}. Se usará el costo por defecto.')
    
    return redirect('provider_zone_costs_manage')


@login_required
def set_current_zone(request):
    """Establecer zona actual del usuario (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    zone_id = request.POST.get('zone_id')
    # NUEVO: Obtener ciudad actual
    current_city = get_current_city(request)
    
    if zone_id:
        try:
            # NUEVO: Validar que la zona pertenezca a la ciudad actual
            zone = Zone.objects.get(id=zone_id, active=True, city=current_city)
            request.session['current_zone_id'] = zone.id
            return JsonResponse({
                'success': True,
                'zone_name': zone.name,
                'message': f'Ubicación establecida en {zone.name}'
            })
        except Zone.DoesNotExist:
            return JsonResponse({'error': 'Zona no encontrada en tu ciudad'}, status=404)
    else:
        # Limpiar zona actual
        request.session.pop('current_zone_id', None)
        return JsonResponse({
            'success': True,
            'message': 'Zona limpiada'
        })


@login_required
def detect_user_location(request):
    """Detectar ubicación del usuario y sugerir zona"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    import json
    data = json.loads(request.body)
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    if not lat or not lng:
        return JsonResponse({'error': 'Coordenadas requeridas'}, status=400)
    
    # NUEVO: Obtener ciudad actual
    current_city = get_current_city(request)
    
    # NUEVO: Buscar en ciudad actual
    user_locations = Location.objects.filter(
        customer=request.user,
        city=current_city
    ).select_related('zone')
    
    closest_location = None
    min_distance = float('inf')
    
    for location in user_locations:
        lat_diff = abs(float(location.latitude) - float(lat))
        lng_diff = abs(float(location.longitude) - float(lng))
        distance = lat_diff + lng_diff
        
        if distance < min_distance:
            min_distance = distance
            closest_location = location
    
    # Si hay ubicación cercana (< 0.01 grados ~ 1km)
    if closest_location and min_distance < 0.01:
        zone = closest_location.zone
        request.session['current_zone_id'] = zone.id
        
        return JsonResponse({
            'success': True,
            'zone_id': zone.id,
            'zone_name': zone.name,
            'location_name': closest_location.label,
            'message': f'Ubicación detectada: {closest_location.label} en {zone.name}'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró una ubicación guardada cercana en {current_city.name}. Por favor selecciona tu zona.',
            'requires_selection': True
        })

@login_required
def provider_coverage_manage(request):
    """Gestión de zonas de cobertura del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar su cobertura')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    
    # Obtener todas las ciudades activas
    cities = City.objects.filter(active=True).order_by('display_order', 'name')
    
    # Zonas actuales del proveedor
    current_zones = provider_profile.coverage_zones.all()
    current_zone_ids = set(current_zones.values_list('id', flat=True))
    
    # Separar zonas cubiertas y disponibles
    covered_zones = current_zones
    
    # ✅ CAMBIO: Convertir selected_city_id a entero si existe
    selected_city_id = request.GET.get('city')
    selected_city = None  # ✅ NUEVO: Variable para la ciudad seleccionada
    available_zones = []
    
    if selected_city_id:
        try:
            selected_city_id = int(selected_city_id)
            selected_city = City.objects.get(id=selected_city_id, active=True)  # ✅ NUEVO
            # Filtrar zonas de la ciudad seleccionada que NO estén ya cubiertas
            available_zones = Zone.objects.filter(
                city_id=selected_city_id, 
                active=True
            ).exclude(
                id__in=current_zone_ids
            ).order_by('name')
        except (ValueError, TypeError, City.DoesNotExist):
            selected_city_id = None  # ✅ NUEVO: Reset si hay error
    
    context = {
        'provider_profile': provider_profile,
        'covered_zones': covered_zones,
        'available_zones': available_zones,
        'cities': cities,
        'selected_city_id': selected_city_id,
        'selected_city': selected_city,  # ✅ NUEVO: Para mostrar en el template
    }
    return render(request, 'providers/coverage_manage.html', context)


@login_required
def provider_coverage_add(request):
    """Agregar zona a la cobertura"""
    if request.method != 'POST':
        return redirect('provider_coverage_manage')
    
    if request.user.profile.role != 'provider':
        messages.error(request, 'No autorizado')
        return redirect('dashboard')
    
    zone_id = request.POST.get('zone_id')
    
    try:
        zone = get_object_or_404(Zone, id=zone_id, active=True)
        provider_profile = request.user.provider_profile
        
        # Agregar zona
        provider_profile.coverage_zones.add(zone)
        
        messages.success(request, f'✅ Zona {zone.name} agregada a tu cobertura')
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Zona agregada a cobertura',
            metadata={'zone': zone.name}
        )
        
    except Exception as e:
        messages.error(request, f'Error al agregar zona: {str(e)}')
    
    return redirect('provider_coverage_manage')


@login_required
def provider_coverage_remove(request, zone_id):
    """Remover zona de la cobertura"""
    if request.method != 'POST':
        return redirect('provider_coverage_manage')
    
    if request.user.profile.role != 'provider':
        messages.error(request, 'No autorizado')
        return redirect('dashboard')
    
    try:
        zone = get_object_or_404(Zone, id=zone_id)
        provider_profile = request.user.provider_profile
        
        # ✅ REMOVIDO: Ya no verificamos que tenga al menos una zona
        # El proveedor puede eliminar todas sus zonas si se equivocó
        
        # Verificar que no tenga reservas activas en esta zona
        active_bookings = Booking.objects.filter(
            provider=request.user,
            location__zone=zone,
            status__in=['pending', 'accepted']
        ).count()
        
        if active_bookings > 0:
            messages.error(
                request,
                f'❌ No puedes eliminar {zone.name} porque tienes {active_bookings} '
                f'reserva(s) activa(s) en esta zona. Completa o cancela primero.'
            )
            return redirect('provider_coverage_manage')
        
        # Remover zona
        provider_profile.coverage_zones.remove(zone)
        
        # Eliminar configuración de costo para esta zona
        ProviderZoneCost.objects.filter(
            provider=request.user,
            zone=zone
        ).delete()
        
        messages.success(request, f'✅ Zona {zone.name} removida de tu cobertura')
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            action='Zona removida de cobertura',
            metadata={'zone': zone.name}
        )
        
    except Exception as e:
        messages.error(request, f'Error al remover zona: {str(e)}')
    
    return redirect('provider_coverage_manage')

@login_required
def payment_process(request, booking_id):
    """
    Vista principal del proceso de pago v2
    Permite al usuario elegir entre PayPhone o Transferencia Bancaria
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    # Verificar que la reserva esté en estado correcto para pagar
    if booking.status not in ['pending', 'accepted']:
        messages.error(request, 'Esta reserva no puede ser pagada en este momento.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Verificar si ya existe un pago
    if booking.payment_status == 'paid':
        messages.info(request, 'Esta reserva ya ha sido pagada.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Calculo de valores e impuestos
    amount_with_tax = booking.sub_total_cost * 100
    service = booking.service * 100
    tax = booking.tax
    amount_without_tax = booking.travel_cost * 100
    
    amount = amount_with_tax + amount_without_tax + tax + service

    context = {
        'booking': booking,
        'amount_with_tax':amount_with_tax,
        'amount_without_tax':amount_without_tax,
        'service':service,
        'tax':tax,
        'amount':amount,
        'payphone_enabled': True,  # Configurar según tus necesidades
        'bank_transfer_enabled': True,
        'PAYPHONE_API_TOKEN':settings.PAYPHONE_API_TOKEN,
        'PAYPHONE_STORE_ID':settings.PAYPHONE_STORE_ID,
    }
    
    return render(request, 'payments/process.html', context)


@login_required
def payment_bank_transfer(request, booking_id):
    """
    Vista COMPLETA para procesar pagos por transferencia bancaria
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    # Verificar que la reserva no esté ya pagada
    if booking.payment_status == 'paid':
        messages.info(request, 'Esta reserva ya ha sido pagada.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Obtener cuentas bancarias activas
    bank_accounts = BankAccount.objects.filter(is_active=True).order_by('display_order')
    
    if request.method == 'POST':
        reference_code = request.POST.get('reference_code', '').strip()
        bank_account_id = request.POST.get('bank_account_id')
        proof_image = request.FILES.get('proof_image')
        
        # Validaciones
        if not bank_account_id:
            messages.error(request, 'Debes seleccionar una cuenta bancaria.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        bank_account = get_object_or_404(BankAccount, id=bank_account_id, is_active=True)
        
        if not reference_code:
            messages.error(request, 'El número de comprobante/referencia es obligatorio.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        if not proof_image:
            messages.error(request, 'Debes subir una imagen del comprobante de pago.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        try:
            # Obtener o crear método de pago
            payment_method, created = PaymentMethod.objects.get_or_create(
                code='bank_transfer',
                defaults={
                    'name': 'Transferencia Bancaria',
                    'description': 'Pago mediante transferencia bancaria',
                    'is_active': True,
                    'requires_proof': True,
                    'requires_reference': True,
                    'display_order': 2,
                    'icon': '🏦'
                }
            )
            
            # Subir comprobante
            proof_url = upload_payment_proof(
                file=proof_image,
                booking_id=str(booking.id)
            )
            
            # Crear registro de comprobante
            payment_proof = PaymentProof.objects.create(
                booking=booking,
                payment_method=payment_method,
                bank_account=bank_account,
                reference_code=reference_code,
                proof_image=proof_url,
                verified=False
            )
            
            # Actualizar estado de la reserva
            booking.payment_status = 'pending_validation'
            booking.save()
            
            # Log de auditoría
            AuditLog.objects.create(
                user=request.user,
                action='Comprobante de transferencia bancaria enviado',
                metadata={
                    'booking_id': str(booking.id),
                    'payment_proof_id': payment_proof.id,
                    'reference_code': reference_code,
                    'bank_account': bank_account.bank_name
                }
            )
            
            # 🔥 NOTIFICACIONES - USANDO TAREAS CELERY
            
            # 1. Email al CLIENTE
            try:
                from core.tasks import send_payment_proof_received_task
                send_payment_proof_received_task.delay(
                    booking_id=str(booking.id),
                    customer_email=booking.customer.email,
                    customer_name=booking.customer.get_full_name() or booking.customer.username,
                    amount=str(booking.total_cost)
                )
            except Exception as e:
                logger.warning(f"Error enviando email al cliente: {e}")
            
            # 2. Email a ADMINS
            try:
                from core.tasks import notify_admin_payment_pending_task
                admin_users = User.objects.filter(is_staff=True, is_active=True)
                admin_emails = [admin.email for admin in admin_users if admin.email]
                
                if admin_emails:
                    notify_admin_payment_pending_task.delay(
                        booking_id=str(booking.id),
                        customer_name=booking.customer.get_full_name() or booking.customer.username,
                        amount=str(booking.total_cost),
                        admin_email_list=admin_emails
                    )
            except Exception as e:
                logger.warning(f"Error enviando notificación a admins: {e}")
            
            # 3. Notificación en el CENTRO (modelo Notification)
            Notification.objects.create(
                user=booking.customer,
                notification_type='payment_received',
                title='💳 Comprobante de Pago Recibido',
                message=f'Hemos recibido tu comprobante de transferencia bancaria. Nuestro equipo lo está validando.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='payment_received',
                title='💳 Comprobante de Pago Pendiente',
                message=f'El cliente {booking.customer.get_full_name()} ha enviado un comprobante de pago. Pendiente de validación.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            messages.success(
                request,
                '✅ Comprobante recibido. Nuestro equipo lo verificará pronto. '
                'Recibirás una notificación cuando esté confirmado.'
            )
            return redirect('payment_confirmation', payment_id=payment_proof.id)
            
        except Exception as e:
            logger.error(f"Error en payment_bank_transfer: {e}")
            messages.error(request, f'Error al subir comprobante: {str(e)}')
    
    return render(request, 'payments/bank_transfer.html', {
        'booking': booking,
        'bank_accounts': bank_accounts,
    })


@login_required
def payment_confirmation(request, payment_id):
    """
    Vista de confirmación después de registrar un pago
    Funciona con PaymentProof o Payment
    """
    # Intenta obtener como PaymentProof primero
    payment_proof = get_object_or_404(PaymentProof, id=payment_id)
    booking = payment_proof.booking
    
    # Verificar que el usuario sea el cliente
    if booking.customer != request.user:
        messages.error(request, 'No tienes acceso a este recurso.')
        return redirect('home')
    
    context = {
        'payment_proof': payment_proof,
        'booking': booking,
        'payment': payment_proof,  # Para compatibilidad con template
    }
    
    return render(request, 'payments/payment_confirmation.html', context)


def notify_admin_pending_payment(payment):
    """
    Envía notificación a los administradores sobre un pago pendiente de validación
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Obtener todos los administradores
    admins = User.objects.filter(is_staff=True, is_active=True)
    
    admin_emails = [admin.email for admin in admins if admin.email]
    
    if admin_emails:
        subject = f'[Liberi] Nuevo pago por validar - Reserva #{payment.booking.id}'
        message = f"""
        Hola Administrador,
        
        Se ha registrado un nuevo pago por transferencia bancaria que requiere validación:
        
        DETALLES DEL PAGO:
        - ID de Pago: {payment.id}
        - ID de Reserva: {payment.booking.id}
        - Cliente: {payment.booking.customer.get_full_name() or payment.booking.customer.username}
        - Monto: ${payment.amount}
        - Número de Referencia: {payment.reference_number or 'N/A'}
        - Fecha de Transferencia: {payment.transfer_date or 'N/A'}
        
        Por favor, revisa el comprobante y valida el pago en el panel de administración:
        {settings.BASE_DIR}/admin/bookings/payment/{payment.id}/change/
        
        ---
        Sistema Liberi
        """
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error enviando email a administradores: {e}")
            # Log the error pero no fallar el proceso


def send_payment_confirmation_email(booking, payment):
    """
    Envía email de confirmación al cliente
    """
    subject = f'Confirmación de Pago - Reserva #{booking.id}'
    message = f"""
    Hola {booking.customer.get_full_name() or booking.customer.username},
    
    Hemos recibido tu comprobante de pago por transferencia bancaria.
    
    DETALLES DE TU RESERVA:
    - Número de Reserva: #{booking.id}
    - Servicio: {booking.get_services_display()}
    - Monto Total: ${booking.total_cost}
    - Fecha Programada: {booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
    
    ESTADO DEL PAGO:
    Tu pago está siendo validado por nuestro equipo. Este proceso generalmente toma entre 1-4 horas hábiles.
    Te notificaremos por email tan pronto como tu pago sea confirmado.
    
    ¿Tienes preguntas? Contáctanos en soporte@liberi.com
    
    ¡Gracias por confiar en Liberi!
    
    ---
    El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.customer.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Error enviando email de confirmación: {e}")


@login_required
def confirm_bank_transfer_payment(request, booking_id):
    """
    Vista simplificada para confirmar que se realizó la transferencia
    (Sin necesidad de subir comprobante en esta versión simplificada)
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    if request.method == 'POST':
        # Crear el registro de pago pendiente
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_cost,
            payment_method='bank_transfer',
            status='pending_validation',
            transaction_id=f"BT-{booking.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            notes=request.POST.get('notes', ''),
        )
        
        # Actualizar el estado de pago de la reserva
        booking.payment_status = 'pending_validation'
        booking.save()
        
        # Enviar notificaciones
        notify_admin_pending_payment(payment)
        send_payment_confirmation_email(booking, payment)
        
        messages.success(
            request, 
            '¡Gracias por tu pago! Nuestro equipo lo está validando. '
            'Recibirás pronto una notificación de que ha sido procesado.'
        )
        
        return redirect('booking_detail', booking_id=booking.id)
    
    return redirect('payment_bank_transfer', booking_id=booking_id)


# ============================================
# APIs para Notificaciones
# ============================================

@login_required
def api_notifications_list(request):
    """Retorna las notificaciones del usuario en formato JSON"""
    notifications = Notification.objects.filter(user=request.user)[:20]
    
    data = {
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'action_url': n.action_url or '#',
                'created_at': n.created_at.strftime('%d/%m/%Y %H:%M'),
            }
            for n in notifications
        ]
    }
    
    return JsonResponse(data)


@login_required
def api_notifications_count(request):
    """Retorna el conteo de notificaciones no leídas"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def api_notification_mark_read(request, notification_id):
    """Marca una notificación como leída"""
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
def api_notifications_mark_all_read(request):
    """Marca todas las notificaciones del usuario como leídas"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


# ============================================
# Funciones Auxiliares para Crear Notificaciones
# ============================================

def create_booking_notification(booking, notification_type):
    """
    Función auxiliar para crear notificaciones relacionadas con reservas
    """
    notification_configs = {
        'booking_created': {
            'user': booking.provider,
            'title': 'Nueva Reserva',
            'message': f'{booking.customer.get_full_name()} ha creado una nueva reserva.',
        },
        'booking_accepted': {
            'user': booking.customer,
            'title': 'Reserva Aceptada',
            'message': f'Tu reserva con {booking.provider.get_full_name()} ha sido aceptada.',
        },
        'booking_rejected': {
            'user': booking.customer,
            'title': 'Reserva Rechazada',
            'message': f'Tu reserva con {booking.provider.get_full_name()} ha sido rechazada.',
        },
        'booking_completed': {
            'user': booking.customer,
            'title': 'Reserva Completada',
            'message': f'Tu reserva con {booking.provider.get_full_name()} ha sido completada. ¡No olvides dejar una reseña!',
        },
    }
    
    config = notification_configs.get(notification_type)
    if config:
        Notification.objects.create(
            user=config['user'],
            notification_type=notification_type,
            title=config['title'],
            message=config['message'],
            booking=booking,
            action_url=f'/bookings/{booking.id}/'
        )

@login_required
def api_upload_image(request):
    '''API endpoint para subir imágenes vía AJAX'''
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    file = request.FILES.get('image')
    folder = request.POST.get('folder', 'general')
    
    if not file:
        return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)
    
    # Validar
    is_valid, error_msg = validate_image(file, max_size_mb=5)
    if not is_valid:
        return JsonResponse({'error': error_msg}, status=400)
    
    try:
        # Subir
        url = upload_image(
            file=file,
            folder=folder,
            user_id=request.user.id,
            unique_name=True
        )
        
        return JsonResponse({
            'success': True,
            'url': url,
            'filename': file.name
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ============================================================================
# PAYMENT VIEWS
# ============================================================================

@csrf_exempt
def payphone_callback(request):
    """
    Callback de PayPhone - Redirige al usuario después del pago
    """
    logger.info("="*50)
    logger.info("INICIANDO PAYPHONE CALLBACK")
    logger.info("="*50)
    logger.info(f"Callback recibido: {request.POST}")
    transaction_id = request.GET.get('id')
    client_transaction_id = request.GET.get('clientTransactionId')
    
    logger.info(f"PayPhone callback - ID: {transaction_id}, ClientTxId: {client_transaction_id}")
    
    # Validar parámetros
    if not transaction_id or not client_transaction_id:
        logger.error("Faltan parámetros en callback")
        messages.error(request, 'Error: Faltan parámetros de pago')
        return redirect('home')

    # Buscar booking
    try:
        booking = Booking.objects.get(id=client_transaction_id)
        logger.info(f"Booking encontrado: {booking.id}")
    except Booking.DoesNotExist:
        logger.error(f"Booking no encontrado: {client_transaction_id}")
        messages.error(request, 'Reserva no encontrada')
        return redirect('home')

    # Confirmar con PayPhone
    headers = {
        'Authorization': f'Bearer {settings.PAYPHONE_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    confirm_url = getattr(
        settings, 
        'PAYPHONE_URL_CONFIRM_PAYPHONE',
        'https://pay.payphonetodoesposible.com/api/button/V2/Confirm'
    )

    try:
        response = requests.post(
            confirm_url,
            headers=headers,
            json={
                'id': int(transaction_id),
                'clientTxId': str(client_transaction_id)
            },
            timeout=15
        )
        
        logger.info(f"PayPhone status: {response.status_code}")
        logger.info(f"PayPhone response: {response.text}")
        
        response.raise_for_status()
        transaction_data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error confirmando PayPhone: {e}")
        logger.error(f"Response: {getattr(e.response, 'text', 'No response')}")
        messages.error(request, 'Error al verificar el pago. Contacta a soporte.')
        return redirect('booking_detail', booking_id=booking.id)

    # Procesar según estado
    transaction_status = transaction_data.get('transactionStatus', 'Unknown')
    logger.info(f"Transaction status: {transaction_status}")
    
    if transaction_status == 'Approved':
        try:
            with transaction.atomic():
                # Verificar si ya está pagado
                if booking.payment_status != 'paid':
                    # Crear registro de pago
                    payment = Payment.objects.create(
                        booking=booking,
                        amount=booking.total_cost,
                        payment_method='payphone',
                        status='completed',
                        transaction_id=transaction_id
                    )
                    logger.info(f"Pago creado: {payment.id}")
                    
                    # Actualizar booking
                    booking.payment_status = 'paid'
                    booking.save()
                    logger.info(f"Booking actualizado a paid: {booking.id}")
                    
                    # Crear notificaciones
                    # ✅ CORRECTO (Lo que debe ser)
                    Notification.objects.create(
                        user=booking.customer,  # ← Cambiar recipient por user
                        notification_type='payment',
                        title='💳 Pago Confirmado',  # ← Agregar title
                        message=f'Tu pago de ${booking.total_cost} ha sido confirmado',
                        booking=booking,  # ← Agregar referencia a la reserva
                        action_url=f'/bookings/{booking.id}/'  # ← Agregar URL
                    )
                    
                    Notification.objects.create(
                        user=booking.provider,  # ← booking.provider YA es un User
                        notification_type='payment',
                        title='💰 Pago Recibido',
                        message=f'Recibiste un pago de ${booking.total_cost} por tu servicio',
                        booking=booking,
                        action_url=f'/bookings/{booking.id}/'
                    )
                    logger.info("Notificaciones creadas")
                    
                    # Enviar emails (opcional - con try/except para que no rompa si falla)
                    try:
                        send_payment_confirmed_to_customer_task.delay(booking.id)
                        send_payment_received_to_provider_task.delay(booking.id)
                        logger.info("Emails encolados")
                    except Exception as email_error:
                        logger.warning(f"No se pudieron enviar emails: {email_error}")
                    
                    messages.success(request, '¡Pago confirmado exitosamente! Tu reserva está activa.')
                else:
                    logger.info(f"Booking ya estaba pagado: {booking.id}")
                    messages.info(request, 'Este pago ya había sido procesado anteriormente.')
                    
        except Exception as e:
            logger.error(f"Error procesando pago aprobado: {e}", exc_info=True)
            messages.error(request, f"Error al procesar el pago. Contacta a soporte: {e}")
            return redirect('booking_detail', booking_id=booking.id)
            
        return redirect('booking_detail', booking_id=booking.id)
    
    else:
        logger.warning(f"Pago no aprobado. Estado: {transaction_status}")
        messages.warning(request, f'El pago no fue aprobado. Estado: {transaction_status}')
        return redirect('booking_detail', booking_id=booking.id)

def confirm_payphone_transaction(transaction_id, client_transaction_id):
    """
    Confirma una transacción con PayPhone
    Retorna: (success_request, success_transaction, payload)
    """
    try:
        headers = {
            'Authorization': f'Bearer {settings.PAYPHONE_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'id': int(transaction_id),
            'clientTxId': client_transaction_id
        }
        
        logger.info(f'Enviando confirmación a {settings.PAYPHONE_URL_CONFIRM_PAYPHONE}')
        logger.info(f'Headers: {headers}')
        logger.info(f'Payload: {payload}')
        
        response = requests.post(
            settings.PAYPHONE_URL_CONFIRM_PAYPHONE,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        logger.info(f'Status Code: {response.status_code}')
        logger.info(f'Response Text: {response.text}')
        
        response.raise_for_status()
        
        data = response.json()
        logger.info(f'Parsed Response: {data}')
        
        # Verificar el estado de la transacción
        success_request = response.status_code == 200
        
        # PayPhone retorna transactionStatus con valores como "Approved", "Rejected", etc
        transaction_status = data.get('transactionStatus') or data.get('status')
        success_transaction = transaction_status == 'Approved'
        
        return success_request, success_transaction, data
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Error en confirm_payphone_transaction: {e}')
        return False, False, {'error': str(e)}

# ============================================================================
# WITHDRAWS VIEWS
# ============================================================================

def calculate_withdrawal(requested_amount, commission_percent):
    """Calcula comisión y monto a pagar"""
    requested = Decimal(str(requested_amount))
    percent = Decimal(str(commission_percent))
    commission_amount = (requested * percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    amount_payable = (requested - commission_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return commission_amount, amount_payable

def get_active_balance(provider):
    """Calcula saldo activo solo de servicios COMPLETADOS por ambas partes"""
    
    # Solo contar servicios completados POR AMBAS PARTES
    qs = Booking.objects.filter(
        provider=provider, 
        status='completed',
        payment_status='paid',
        provider_completed_at__isnull=False,  # ← Proveedor confirmó
        customer_completed_at__isnull=False,  # ← Cliente confirmó
    )
    earned = qs.aggregate(total=Sum(F('sub_total_cost') + F('travel_cost')))['total'] or Decimal('0.00')
    
    completed_withdrawals = WithdrawalRequest.objects.filter(
        provider=provider,
        status='completed'
    ).aggregate(total=Sum('amount_payable'))['total'] or Decimal('0.00')
    
    pending_withdrawals = WithdrawalRequest.objects.filter(
        provider=provider,
        status='pending'
    ).aggregate(total=Sum('requested_amount'))['total'] or Decimal('0.00')
    
    return earned - completed_withdrawals - pending_withdrawals


def check_withdrawal_limits(provider):
    """Verifica si el proveedor puede hacer un retiro hoy"""
    from django.conf import settings
    
    today = timezone.now().date()
    
    # Verificar retiros de hoy
    today_withdrawals = WithdrawalRequest.objects.filter(
        provider=provider,
        created_at__date=today,
        status__in=['pending', 'completed']
    ).count()
    
    max_per_day = settings.LIBERI_WITHDRAWAL_MAX_PER_DAY
    if today_withdrawals >= max_per_day:
        return False, f"Ya realizaste {today_withdrawals} retiro(s) hoy. Máximo: {max_per_day} por día"
    
    return True, None


def check_weekly_withdrawal_limit(provider, amount):
    """Verifica si el retiro no excede el límite semanal"""
    from django.conf import settings
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())  # Lunes de esta semana
    
    # Sumar retiros de esta semana
    weekly_total = WithdrawalRequest.objects.filter(
        provider=provider,
        created_at__date__gte=week_start,
        status__in=['pending', 'completed']
    ).aggregate(total=Sum('requested_amount'))['total'] or Decimal('0.00')
    
    weekly_limit = Decimal(str(settings.LIBERI_WITHDRAWAL_WEEKLY_LIMIT))
    new_total = weekly_total + Decimal(str(amount))
    
    if new_total > weekly_limit:
        remaining = weekly_limit - weekly_total
        return False, f"Límite semanal: ${weekly_limit}. Ya has retirado ${weekly_total}. Puedes retirar máximo: ${remaining}"
    
    return True, None

@login_required
def provider_bank_accounts(request):
    """Gestión de cuentas bancarias del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder')
        return redirect('dashboard')
    
    bank_accounts = ProviderBankAccount.objects.filter(provider=request.user)
    banks = Bank.objects.all().order_by('name')
    
    if request.method == 'POST':
        bank_id = request.POST.get('bank_id')
        account_type = request.POST.get('account_type')
        account_number = request.POST.get('account_number')
        owner_fullname = request.POST.get('owner_fullname')
        is_primary = request.POST.get('is_primary') == 'on'
        
        # Validar banco
        if not bank_id:
            messages.error(request, 'Selecciona un banco')
            return render(request, 'providers/bank_accounts.html', {
                'bank_accounts': bank_accounts,
                'banks': banks,
                'account_types': [('checking', 'Cuenta Corriente'), ('savings', 'Cuenta de Ahorros')]
            })
        
        # Enmascarar número
        account_masked = f"{account_number[:4]}****{account_number[-4:]}" if len(account_number) > 8 else account_number
        
        try:
            bank = Bank.objects.get(id=bank_id, is_active=True)
            
            # Si es primaria, desmarcar otras
            if is_primary:
                ProviderBankAccount.objects.filter(provider=request.user).update(is_primary=False)
            
            account = ProviderBankAccount.objects.create(
                provider=request.user,
                bank=bank,
                account_type=account_type,
                account_number_masked=account_masked,
                owner_fullname=owner_fullname,
                is_primary=is_primary
            )
            
            AuditLog.objects.create(
                user=request.user,
                action='Cuenta bancaria agregada',
                metadata={'bank': bank.name}
            )
            
            messages.success(request, 'Cuenta bancaria agregada')
            return redirect('provider_bank_accounts')
        except Bank.DoesNotExist:
            messages.error(request, 'Banco no válido')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'bank_accounts': bank_accounts,
        'banks': banks,
        'account_types': [('checking', 'Cuenta Corriente'), ('savings', 'Cuenta de Ahorros')]
    }
    return render(request, 'providers/bank_accounts.html', context)


@login_required
def provider_bank_account_delete(request, account_id):
    """Eliminar cuenta bancaria"""
    account = get_object_or_404(ProviderBankAccount, id=account_id, provider=request.user)
    
    if request.method == 'POST':
        account.delete()
        messages.success(request, 'Cuenta eliminada')
    
    return redirect('provider_bank_accounts')


@login_required
def provider_withdrawal_list(request):
    """Listado de retiros del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder')
        return redirect('dashboard')
    
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')
    active_balance = get_active_balance(request.user)
    
    context = {
        'withdrawals': withdrawals,
        'active_balance': active_balance
    }
    return render(request, 'providers/withdrawals_list.html', context)


@login_required
def provider_withdrawal_create(request):
    """Crear solicitud de retiro"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder')
        return redirect('dashboard')
    
    active_balance = get_active_balance(request.user)
    bank_accounts = ProviderBankAccount.objects.filter(provider=request.user).select_related('bank')
    commission_percent = Decimal(settings.LIBERI_WITHDRAWAL_COMMISSION_PERCENT or '4.0')
    weekly_limit = Decimal(str(settings.LIBERI_WITHDRAWAL_WEEKLY_LIMIT or '500.0'))
    
    # Verificar si puede hacer retiro hoy
    can_withdraw_today, error_msg = check_withdrawal_limits(request.user)
    
    if request.method == 'POST':
        # Validación 1: Puede retirar hoy?
        if not can_withdraw_today:
            messages.error(request, error_msg)
            return render(request, 'providers/withdrawal_create.html', {
                'active_balance': active_balance,
                'bank_accounts': bank_accounts,
                'commission_percent': commission_percent,
                'weekly_limit': weekly_limit,
                'can_withdraw_today': can_withdraw_today,
                'error_msg': error_msg
            })
        
        bank_account_id = request.POST.get('bank_account_id')
        requested_amount = Decimal(request.POST.get('requested_amount', 0))
        description = request.POST.get('description', '')
        
        # Validación 2: Cuenta seleccionada?
        if not bank_account_id:
            messages.error(request, 'Selecciona una cuenta bancaria')
            return render(request, 'providers/withdrawal_create.html', {
                'active_balance': active_balance,
                'bank_accounts': bank_accounts,
                'commission_percent': commission_percent,
                'weekly_limit': weekly_limit,
                'can_withdraw_today': can_withdraw_today
            })
        
        # Validación 3: Monto válido?
        if requested_amount <= 0:
            messages.error(request, 'El monto debe ser mayor a 0')
            return render(request, 'providers/withdrawal_create.html', {
                'active_balance': active_balance,
                'bank_accounts': bank_accounts,
                'commission_percent': commission_percent,
                'weekly_limit': weekly_limit,
                'can_withdraw_today': can_withdraw_today
            })
        
        # Validación 4: Saldo suficiente?
        if requested_amount > active_balance:
            messages.error(request, f'Saldo insuficiente. Disponible: ${active_balance}')
            return render(request, 'providers/withdrawal_create.html', {
                'active_balance': active_balance,
                'bank_accounts': bank_accounts,
                'commission_percent': commission_percent,
                'weekly_limit': weekly_limit,
                'can_withdraw_today': can_withdraw_today
            })
        
        # Validación 5: Límite semanal?
        can_withdraw_weekly, weekly_error = check_weekly_withdrawal_limit(request.user, requested_amount)
        if not can_withdraw_weekly:
            messages.error(request, weekly_error)
            return render(request, 'providers/withdrawal_create.html', {
                'active_balance': active_balance,
                'bank_accounts': bank_accounts,
                'commission_percent': commission_percent,
                'weekly_limit': weekly_limit,
                'can_withdraw_today': can_withdraw_today,
                'weekly_error': weekly_error
            })
        
        try:
            bank_account = ProviderBankAccount.objects.get(id=bank_account_id, provider=request.user)
            
            # Calcular comisión
            commission_amount, amount_payable = calculate_withdrawal(requested_amount, commission_percent)
            
            # Crear solicitud
            withdrawal = WithdrawalRequest.objects.create(
                provider=request.user,
                provider_bank_account=bank_account,
                requested_amount=requested_amount,
                commission_percent=commission_percent,
                commission_amount=commission_amount,
                amount_payable=amount_payable,
                description=description,
                status='pending'
            )
            
            # Notificar admins
            admin_users = User.objects.filter(is_staff=True, is_active=True)
            admin_emails = [a.email for a in admin_users if a.email]
            
            if admin_emails:
                try:
                    send_mail(
                        subject=f'💰 Nueva Solicitud de Retiro - {request.user.get_full_name()}',
                        message=f"""
Nuevo retiro solicitado:

Proveedor: {request.user.get_full_name()}
Monto Solicitado: ${requested_amount}
Comisión (4%): ${commission_amount}
A Pagar: ${amount_payable}
Banco: {bank_account.bank.name}
Cuenta: {bank_account.account_number_masked}

Revisa en admin: /admin/core/withdrawalrequest/{withdrawal.id}/change/
                        """,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=admin_emails,
                        fail_silently=True
                    )
                except:
                    pass
            
            AuditLog.objects.create(
                user=request.user,
                action='Solicitud de retiro creada',
                metadata={'amount': str(requested_amount), 'commission': str(commission_amount)}
            )
            
            messages.success(request, '✅ Solicitud de retiro creada. Espera la validación del equipo.')
            return redirect('provider_withdrawal_list')
            
        except ProviderBankAccount.DoesNotExist:
            messages.error(request, 'Cuenta no encontrada')
    
    context = {
        'active_balance': active_balance,
        'bank_accounts': bank_accounts,
        'commission_percent': commission_percent,
        'weekly_limit': weekly_limit,
        'can_withdraw_today': can_withdraw_today,
        'error_msg': error_msg if not can_withdraw_today else None
    }
    return render(request, 'providers/withdrawal_create.html', context)

# ============================================================================
# FRONTEND/VIEWS.PY - NUEVAS VISTAS
# Agregar estas vistas al final del archivo
# ============================================================================

@login_required
def booking_complete_with_code(request, booking_id):
    """
    Vista para que el proveedor complete el servicio ingresando el código
    """
    if request.method != 'POST':
        return redirect('booking_detail', booking_id=booking_id)
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el proveedor
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Verificar estado
    if booking.status != 'accepted':
        messages.error(request, 'Esta reserva no está en estado aceptado')
        return redirect('booking_detail', booking_id=booking_id)
    
    if booking.payment_status != 'paid':
        messages.error(request, 'Esta reserva no ha sido pagada')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Obtener código ingresado
    code = request.POST.get('completion_code', '').strip()
    
    if not code:
        messages.error(request, 'Debes ingresar el código de finalización')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Verificar código
    if not booking.verify_completion_code(code):
        messages.error(request, 'Código incorrecto. Verifica con el cliente.')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Marcar como completado
    try:
        with transaction.atomic():
            booking.status = 'completed'
            booking.provider_completed_at = timezone.now()
            booking.customer_completed_at = timezone.now()  # Ambos confirmados con código
            booking.save()
            
            # Notificaciones
            Notification.objects.create(
                user=booking.customer,
                notification_type='booking_completed',
                title='✅ Servicio Completado',
                message=f'Tu servicio con {booking.provider.get_full_name()} ha sido completado exitosamente.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='booking_completed',
                title='✅ Servicio Completado',
                message=f'Has completado el servicio con {booking.customer.get_full_name()}. El dinero estará disponible para retiro.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Servicio completado con código',
                metadata={
                    'booking_id': str(booking.id),
                    'code_verified': True
                }
            )
            
            messages.success(request, '✅ ¡Servicio completado! El código fue verificado correctamente.')
            
    except Exception as e:
        logger.error(f"Error completando servicio: {e}")
        messages.error(request, 'Error al completar el servicio. Intenta nuevamente.')
    
    return redirect('booking_detail', booking_id=booking_id)


@login_required
def booking_report_incident(request, booking_id):
    """
    Vista para que el cliente reporte que no recibió el servicio
    """
    if request.method != 'POST':
        return redirect('booking_detail', booking_id=booking_id)
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Verificar que sea el cliente
    if booking.customer != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Verificar que no haya sido reportado ya
    if booking.incident_reported:
        messages.info(request, 'Ya has reportado una incidencia para esta reserva')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Obtener descripción
    description = request.POST.get('incident_description', '').strip()
    
    if not description:
        messages.error(request, 'Debes describir qué sucedió')
        return redirect('booking_detail', booking_id=booking_id)
    
    try:
        with transaction.atomic():
            # Registrar incidencia
            booking.incident_reported = True
            booking.incident_description = description
            booking.incident_reported_at = timezone.now()
            booking.save()
            
            # Notificar al proveedor
            Notification.objects.create(
                user=booking.provider,
                notification_type='system',
                title='⚠️ Incidencia Reportada',
                message=f'El cliente {booking.customer.get_full_name()} reportó una incidencia: {description[:100]}',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            # Notificar a los administradores
            admin_users = User.objects.filter(is_staff=True, is_active=True)
            
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    notification_type='system',
                    title='🚨 Nueva Incidencia Reportada',
                    message=f'Reserva #{str(booking.id)[:8]} - Cliente: {booking.customer.get_full_name()}',
                    booking=booking,
                    action_url=f'/admin/core/booking/{booking.id}/change/'
                )
            
            # Enviar email a admins
            admin_emails = [admin.email for admin in admin_users if admin.email]
            
            if admin_emails:
                try:
                    from core.tasks import send_incident_notification_to_admins_task
                    send_incident_notification_to_admins_task.delay(
                        booking_id=str(booking.id),
                        admin_emails=admin_emails
                    )
                except Exception as e:
                    logger.warning(f"Error enviando email de incidencia: {e}")
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Incidencia reportada',
                metadata={
                    'booking_id': str(booking.id),
                    'description': description
                }
            )
            
            messages.success(
                request,
                '✅ Incidencia reportada. Nuestro equipo revisará el caso y te contactará pronto.'
            )
            
    except Exception as e:
        logger.error(f"Error reportando incidencia: {e}")
        messages.error(request, 'Error al reportar la incidencia. Intenta nuevamente.')
    
    return redirect('booking_detail', booking_id=booking_id)

# ============================================
# NUEVAS VISTAS PARA UBICACIONES
# ============================================

@login_required
def provider_locations_list(request):
    """Lista todas las ubicaciones del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    # ✅ VALIDACIÓN: Debe elegir modalidad primero
    provider_profile = request.user.provider_profile
    if provider_profile.service_mode not in ['home', 'local', 'both']:
        messages.warning(request, '⚠️ Primero debes elegir tu modalidad de atención')
        return redirect('provider_settings_service_mode')
    
    from apps.core.models import ProviderLocation
    
    locations = ProviderLocation.objects.filter(
        provider=request.user
    ).select_related('city', 'zone').order_by('location_type')
    
    base_location = locations.filter(location_type='base').first()
    local_locations = locations.filter(location_type='local')
    
    context = {
        'base_location': base_location,
        'local_locations': local_locations,
        'all_locations': locations,
        'service_mode': provider_profile.service_mode,  # Pasar modalidad al template
    }
    return render(request, 'providers/locations_list.html', context)


@login_required
def provider_location_create(request, loc_type=None):
    """Crear nueva ubicación con validaciones de modalidad"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    # ✅ VALIDACIÓN 1: Debe tener modalidad configurada
    provider_profile = request.user.provider_profile
    if provider_profile.service_mode not in ['home', 'local', 'both']:
        messages.warning(request, '⚠️ Primero debes elegir tu modalidad de atención')
        return redirect('provider_settings_service_mode')
    
    # ✅ VALIDACIÓN 2: Verificar si puede crear este tipo según su modalidad
    service_mode = provider_profile.service_mode
    
    if loc_type == 'base':
        # Solo puede crear domicilio base si modalidad es 'home' o 'both'
        if service_mode == 'local':
            messages.error(request, '❌ Tu modalidad "Solo en Local" no permite domicilio base. Cambia tu modalidad primero.')
            return redirect('provider_locations_list')
        
        # Verificar que no tenga ya un domicilio base
        if ProviderLocation.objects.filter(provider=request.user, location_type='base').exists():
            messages.error(request, 'Ya tienes un domicilio base registrado')
            return redirect('provider_locations_list')
    
    elif loc_type == 'local':
        # Solo puede crear local si modalidad es 'local' o 'both'
        if service_mode == 'home':
            messages.error(request, '❌ Tu modalidad "Solo a Domicilio" no permite locales. Cambia tu modalidad primero.')
            return redirect('provider_locations_list')
    
    if request.method == 'POST':
        form = ProviderLocationForm(
            request.POST,
            request.FILES,
            provider=request.user,
            location_type=loc_type
        )
        if form.is_valid():
            location = form.save(commit=False)
            location.provider = request.user
            location.is_verified = True  # ✅ Auto-verificar (temporal, hasta implementar aprobación)
            location.save()
            messages.success(request, f'✅ {location.label} creado y publicado exitosamente')
            return redirect('provider_locations_list')
    else:
        form = ProviderLocationForm(provider=request.user, location_type=loc_type)
    
    type_name = 'Domicilio Base' if loc_type == 'base' else 'Local/Sucursal'
    context = {
        'form': form,
        'location_type': loc_type,
        'type_display': type_name
    }
    return render(request, 'providers/location_form.html', context)


@login_required
def provider_location_edit(request, loc_id):
    """Editar ubicación"""
    
    location = get_object_or_404(ProviderLocation, id=loc_id, provider=request.user)
    
    if request.method == 'POST':
        form = ProviderLocationForm(
            request.POST,
            instance=location,
            provider=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Actualizado')
            return redirect('provider_locations_list')
    else:
        form = ProviderLocationForm(instance=location, provider=request.user)
    
    context = {'form': form, 'location': location}
    return render(request, 'providers/location_form.html', context)


@login_required
def provider_location_delete(request, loc_id):
    """Eliminar ubicación"""
    from apps.core.models import ProviderLocation
    
    location = get_object_or_404(ProviderLocation, id=loc_id, provider=request.user)
    
    if request.method == 'POST':
        active_bookings = Booking.objects.filter(
            provider=request.user,
            provider_location=location,
            status__in=['pending', 'accepted']
        ).count()
        
        if active_bookings > 0:
            messages.error(request, f'❌ {active_bookings} reserva(s) activa(s)')
            return redirect('provider_locations_list')
        
        location_label = location.label
        location.delete()
        messages.success(request, f'✅ {location_label} eliminado')
        return redirect('provider_locations_list')
    
    context = {'location': location}
    return render(request, 'providers/location_confirm_delete.html', context)


@login_required
def provider_settings_service_mode(request):
    """Configurar modalidad de atención con validaciones"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    
    # Obtener ubicaciones existentes
    from apps.core.models import ProviderLocation
    has_base = ProviderLocation.objects.filter(provider=request.user, location_type='base').exists()
    has_locals = ProviderLocation.objects.filter(provider=request.user, location_type='local').exists()
    
    if request.method == 'POST':
        form = ProviderProfileServiceModeForm(request.POST, instance=provider_profile)
        if form.is_valid():
            new_mode = form.cleaned_data['service_mode']
            
            # ✅ VALIDACIÓN: Verificar compatibilidad con ubicaciones existentes
            if new_mode == 'home' and has_locals:
                messages.error(request, '❌ No puedes seleccionar "Solo a Domicilio" porque tienes locales registrados. Elimínalos primero.')
                return redirect('provider_settings_service_mode')
            
            if new_mode == 'local' and has_base:
                messages.error(request, '❌ No puedes seleccionar "Solo en Local" porque tienes domicilio base registrado. Elimínalo primero.')
                return redirect('provider_settings_service_mode')
            
            form.save()
            messages.success(request, '✅ Modalidad configurada correctamente')
            return redirect('provider_locations_list')
    else:
        form = ProviderProfileServiceModeForm(instance=provider_profile)
    
    context = {
        'form': form,
        'has_base': has_base,
        'has_locals': has_locals,
    }
    return render(request, 'providers/service_mode_form.html', context)


# ============================================
# APIS AJAX
# ============================================

@login_required
def api_get_service_locations(request):
    """Obtiene ubicaciones para un servicio"""
    from apps.core.models import ProviderLocation
    
    service_id = request.GET.get('service_id')
    zone_id = request.GET.get('zone_id')
    service_mode = request.GET.get('service_mode', 'home')
    
    if not service_id:
        return JsonResponse({'error': 'service_id requerido'}, status=400)
    
    try:
        service = Service.objects.get(id=service_id, available=True)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)
    
    provider = service.provider
    locations = ProviderLocation.objects.filter(provider=provider)
    
    if zone_id:
        locations = locations.filter(zone_id=zone_id)
    
    if service_mode == 'home':
        locations = locations.filter(location_type='base')
    elif service_mode == 'local':
        locations = locations.filter(location_type='local', is_verified=True)
    
    locations = locations.select_related('zone', 'city')
    
    data = {
        'success': True,
        'count': locations.count(),
        'locations': [
            {
                'id': loc.id,
                'label': loc.label,
                'address': loc.address,
                'type': loc.get_location_type_display(),
            }
            for loc in locations
        ]
    }
    return JsonResponse(data)


@login_required
def api_get_zones_by_city(request):
    """Obtiene zonas por ciudad (para formulario de ubicaciones)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requerido'}, status=405)
    
    city_id = request.POST.get('city_id')
    if not city_id:
        return JsonResponse({'error': 'city_id requerido'}, status=400)
    
    try:
        city = City.objects.get(id=city_id, active=True)
        zones = Zone.objects.filter(city=city, active=True).order_by('name')
        
        data = {
            'success': True,
            'zones': [{'id': z.id, 'name': z.name} for z in zones]
        }
        return JsonResponse(data)
    except City.DoesNotExist:
        return JsonResponse({'error': 'No encontrada'}, status=404)