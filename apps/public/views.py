from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.http import JsonResponse
from decimal import Decimal
from django.utils import timezone
import logging

from apps.core.models import (
    Service, Category, ProviderProfile, Review, Booking,
    Location, Zone, City, ProviderZoneCost, SystemConfig,
    ProviderLocation
)
from apps.core.utils import get_current_city

logger = logging.getLogger(__name__)

def get_active_categories():
    return Category.objects.all().order_by('name')

def set_current_city(request, city):
    """Establece la ciudad actual en sesión y perfil"""
    request.session['current_city_id'] = city.id
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        request.user.profile.current_city = city
        request.user.profile.save(update_fields=['current_city'])


def home(request):
    """Página de inicio"""
    # Obtener ciudad actual
    current_city = get_current_city(request)
    
    # Servicios destacados de la ciudad actual
    featured_services = Service.objects.filter(
        available=True,
        provider__provider_profile__status='approved',
        provider__provider_profile__is_active=True
    )
    
    if current_city:
        featured_services = featured_services.filter(
            provider__provider_profile__coverage_zones__city=current_city
        )
    
    featured_services = featured_services.select_related('provider').distinct()[:6]
    
    context = {
        'categories': get_active_categories(),
        'featured_services': featured_services,
        'current_city': current_city,
        'cities': City.objects.filter(active=True).order_by('display_order'),
    }
    return render(request, 'home.html', context)


def services_list(request):
    """Listado de servicios con filtros mejorados por ciudad y zona"""
    services = Service.objects.filter(available=True).select_related('provider')
    
    # Obtener ciudad actual
    current_city = get_current_city(request)
    
    # Cambiar ciudad si se solicita
    city_id = request.GET.get('city')
    if city_id:
        try:
            current_city = City.objects.get(id=city_id, active=True)
            set_current_city(request, current_city)
        except City.DoesNotExist:
            pass
    
    # Obtener zonas de la ciudad actual
    zones = Zone.objects.filter(
        active=True,
        city=current_city
    ).order_by('name') if current_city else Zone.objects.none()
    
    # Obtener zona actual
    current_zone_id = request.session.get('current_zone_id')
    current_zone = zones.filter(id=current_zone_id).first() if current_zone_id else None
    
    # Si no hay zona en sesión, intentar obtener de la última ubicación
    if not current_zone and current_city and request.user.is_authenticated:
        last_location = Location.objects.filter(
            customer=request.user,
            city=current_city
        ).select_related('zone').order_by('-created_at').first()
        
        if last_location and last_location.zone:
            current_zone = last_location.zone
            request.session['current_zone_id'] = current_zone.id
    
    # Obtener modalidad seleccionada
    service_mode = request.GET.get('service_mode', 'home')
    if service_mode not in ['home', 'local']:
        service_mode = 'home'
    
    # Filtros
    category_id = request.GET.get('category')
    search = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    # ✅ MANEJO DE ZONA: establecer o limpiar
    clear_zone = request.GET.get('clear_zone')
    zone_id = request.GET.get('zone')

    if clear_zone == '1':
        # Usuario quiere cambiar de zona - limpiar sesión
        request.session.pop('current_zone_id', None)
        current_zone = None
    elif zone_id:
        # Usuario está seleccionando una nueva zona
        try:
            zone = zones.get(id=zone_id)
            current_zone = zone
            request.session['current_zone_id'] = zone.id
        except Zone.DoesNotExist:
            pass
    
    # FILTRO PRINCIPAL: Solo servicios de proveedores que cubren la ciudad
    if current_city:
        services = services.filter(
            provider__provider_profile__coverage_zones__city=current_city,
            provider__provider_profile__is_active=True,
            provider__provider_profile__status='approved'
        )
    
    # FILTRAR POR MODALIDAD
    if service_mode == 'home':
        services = services.filter(
            Q(provider__provider_profile__service_mode='home') |
            Q(provider__provider_profile__service_mode='both')
        )
    elif service_mode == 'local':
        services = services.filter(
            Q(provider__provider_profile__service_mode='local') |
            Q(provider__provider_profile__service_mode='both')
        )
        
        # Filtrar solo proveedores que tienen locales verificados en la zona actual
        if current_zone:
            providers_with_locals_in_zone = ProviderLocation.objects.filter(
                location_type='local',
                is_verified=True,
                zone=current_zone
            ).values_list('provider_id', flat=True).distinct()
            
            services = services.filter(provider_id__in=providers_with_locals_in_zone)
    
    # FILTRO SECUNDARIO: Por zona específica (cobertura) - SOLO PARA MODO HOME
    if current_zone and service_mode == 'home':
        services = services.filter(
            provider__provider_profile__coverage_zones=current_zone
        )
    
    if category_id:
        services = services.filter(provider__provider_profile__category_id=category_id)
    
    if search:
        services = services.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search) |
            Q(provider__provider_profile__business_name__icontains=search)
        )
    
    if min_price:
        services = services.filter(base_price__gte=min_price)
    
    if max_price:
        services = services.filter(base_price__lte=max_price)
    
    services = services.filter(
        provider__provider_profile__status='approved',
        provider__provider_profile__is_active=True
    ).distinct()
    
    # Agregar rating promedio y costo de movilización por zona
    for service in services:
        # Rating
        rating = Review.objects.filter(
            booking__provider=service.provider
        ).aggregate(Avg('rating'))
        service.provider_rating = round(rating['rating__avg'] or 0, 1)
        
        # Costo de movilización según zona actual (solo para modo home)
        if current_zone and service_mode == 'home':
            zone_cost = ProviderZoneCost.objects.filter(
                provider=service.provider,
                zone=current_zone
            ).first()
            
            if zone_cost:
                service.travel_cost = zone_cost.travel_cost
            else:
                service.travel_cost = SystemConfig.get_config('default_travel_cost', 2.50)
        else:
            service.travel_cost = 0
    
    context = {
        'services': services,
        'categories': get_active_categories(),
        'zones': zones,
        'current_zone': current_zone,
        'current_city': current_city,
        'service_mode': service_mode,
        'cities': City.objects.filter(active=True).order_by('display_order'),
        'selected_category': Category.objects.filter(id=category_id).first() if category_id else None,
        'show_zone_warning': not current_zone and current_city,
    }
    return render(request, 'services/list.html', context)


@login_required
def set_current_city_ajax(request):
    """Establecer ciudad actual (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    city_id = request.POST.get('city_id')
    
    if city_id:
        try:
            city = City.objects.get(id=city_id, active=True)
            set_current_city(request, city)
            
            # Limpiar zona actual al cambiar ciudad
            request.session.pop('current_zone_id', None)
            
            return JsonResponse({
                'success': True,
                'city_name': city.name,
                'message': f'Ciudad establecida en {city.name}'
            })
        except City.DoesNotExist:
            return JsonResponse({'error': 'Ciudad no encontrada'}, status=404)
    else:
        return JsonResponse({'error': 'Ciudad requerida'}, status=400)


def service_detail(request, service_code):
    """Detalle de un servicio con validación de zona y modalidad MEJORADA"""
    
    service = get_object_or_404(Service, service_code=service_code)
    provider_profile = service.provider.provider_profile
    
    # Obtener ciudad actual
    current_city = get_current_city(request)
    
    # Obtener zona actual
    current_zone_id = request.session.get('current_zone_id')
    current_zone = Zone.objects.filter(id=current_zone_id).first() if current_zone_id else None
    
    # ✅ OBTENER ZONAS DISPONIBLES (para selector)
    zones = Zone.objects.filter(
        active=True,
        city=current_city
    ).order_by('name') if current_city else Zone.objects.none()
    
    # ✅ Si viene zone_id en GET, establecerla
    zone_id = request.GET.get('zone')
    if zone_id:
        try:
            zone = zones.get(id=zone_id)
            current_zone = zone
            request.session['current_zone_id'] = zone.id
        except Zone.DoesNotExist:
            pass
    
    # ✅ DETERMINAR MODALIDAD DEL PROVEEDOR
    provider_service_mode = provider_profile.service_mode
    
    # ✅ OBTENER MODO SELECCIONADO POR USUARIO (si viene de buscador)
    selected_mode = request.GET.get('service_mode')
    
    # ✅ OBTENER LOCATION_ID SI VIENE EN URL (para pre-selección)
    selected_location_id = request.GET.get('location_id')
    
    # ✅ VALIDAR Y AJUSTAR selected_mode SEGÚN MODALIDAD DEL PROVEEDOR
    if provider_service_mode == 'home':
        selected_mode = 'home'
        user_can_choose = False
    elif provider_service_mode == 'local':
        selected_mode = 'local'
        user_can_choose = False
    elif provider_service_mode == 'both':
        user_can_choose = True
        if not selected_mode or selected_mode not in ['home', 'local']:
            selected_mode = 'home'  # Default
    else:
        selected_mode = None
        user_can_choose = False
    
    # ✅ OBTENER UBICACIONES DISPONIBLES SEGÚN MODO
    available_provider_locations = []
    selected_provider_location = None
    provider_has_required_location = False
    
    logger.info(f"=== DEBUG service_detail ===")
    logger.info(f"Provider: {service.provider.username}")
    logger.info(f"Current city: {current_city.name if current_city else 'NONE'}")
    logger.info(f"Current zone: {current_zone.name if current_zone else 'NONE'}")
    logger.info(f"Selected mode: {selected_mode}")
    logger.info(f"Provider service mode: {provider_service_mode}")
    
    if selected_mode:
        if selected_mode == 'home':
            # Modo domicilio - si tiene zonas de cobertura, puede atender
            # Ya no requerimos ubicación base para modo home
            provider_has_required_location = provider_profile.coverage_zones.exists()
            logger.info(f"Modo HOME - Has coverage zones: {provider_has_required_location}")
            
        elif selected_mode == 'local':
            # Modo local - obtener locales verificados del proveedor
            # ✅ NO FILTRAR POR ZONA - Mostrar todos los locales de la ciudad
            location_filter = ProviderLocation.objects.filter(
                provider=service.provider,
                location_type='local',
                is_verified=True
            )
            
            # Filtrar por ciudad actual SI existe
            if current_city:
                location_filter = location_filter.filter(zone__city=current_city)
                logger.info(f"Filtrando locales por ciudad: {current_city.name}")
            
            available_provider_locations = list(location_filter.select_related('zone', 'zone__city'))
            logger.info(f"Locales disponibles: {len(available_provider_locations)}")
            
            provider_has_required_location = len(available_provider_locations) > 0
            
            # Pre-seleccionar ubicación si viene en URL
            if selected_location_id and available_provider_locations:
                selected_provider_location = next(
                    (loc for loc in available_provider_locations if str(loc.id) == str(selected_location_id)),
                    None
                )
                logger.info(f"Pre-selección por URL - Location ID: {selected_location_id}, Found: {selected_provider_location is not None}")
            
            # Si no hay selección, tomar el primero por defecto
            if not selected_provider_location and available_provider_locations:
                selected_provider_location = available_provider_locations[0]
                logger.info(f"Auto-selección del primer local: {selected_provider_location.label}")
    
    logger.info(f"=== FIN DEBUG ===")

    
    # ✅ VERIFICAR SI PUEDE RESERVAR - LÓGICA MEJORADA
    can_book = False
    zone_not_covered = False
    zone_required = False  # Nueva variable
    travel_cost = 0
    
    if selected_mode == 'home':
        # Modo domicilio - SÍ REQUIERE ZONA
        zone_required = True
        
        if current_zone:
            provider_covers_zone = provider_profile.coverage_zones.filter(
                id=current_zone.id
            ).exists()
            
            if provider_covers_zone and provider_has_required_location:
                can_book = True
                
                # Calcular costo de traslado
                zone_cost = ProviderZoneCost.objects.filter(
                    provider=service.provider,
                    zone=current_zone
                ).first()
                
                if zone_cost:
                    travel_cost = zone_cost.travel_cost
                else:
                    travel_cost = Decimal(SystemConfig.get_config('default_travel_cost', 2.50))
            else:
                if not provider_covers_zone:
                    zone_not_covered = True
                else:
                    can_book = False
        else:
            # No hay zona - marcar como requerida
            can_book = False
            
    elif selected_mode == 'local':
        # Modo local - NO REQUIERE ZONA
        zone_required = False
        
        # Puede reservar si hay locales disponibles y ha seleccionado uno
        if provider_has_required_location and selected_provider_location:
            can_book = True
            travel_cost = 0  # Sin costo de traslado
        else:
            can_book = False
    
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
    
    # Ubicaciones del usuario que coincidan con zonas del proveedor (solo para modo home)
    user_locations = []
    valid_locations = []
    if request.user.is_authenticated and selected_mode == 'home':
        user_locations = Location.objects.filter(customer=request.user).select_related('zone')
        provider_zone_ids = provider_profile.coverage_zones.values_list('id', flat=True)
        valid_locations = [loc for loc in user_locations if loc.zone_id in provider_zone_ids]
    
    # Calcular costo total
    total_cost = service.base_price + Decimal(str(travel_cost))

    # Meta tags
    meta_image = request.build_absolute_uri(service.primary_image.url) if service.primary_image else None
    
    context = {
        'service': service,
        'meta_image': meta_image,
        'meta_title': f"{service.name} | Liberi",
        'meta_description': (service.description[:160] if service.description else "Servicio verificado en Liberi"),
        'reviews': reviews,
        'provider_rating': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'user_locations': user_locations,
        'valid_locations': valid_locations,
        'travel_cost': travel_cost,
        'total_cost': total_cost,
        'today': timezone.now().date(),
        'current_zone': current_zone,
        'current_city': current_city,
        'zones': zones,  # ✅ NUEVO: Zonas para selector
        'can_book': can_book,
        'zone_not_covered': zone_not_covered,
        'zone_required': zone_required,  # ✅ NUEVO: Indica si se requiere zona
        # Variables de modalidad
        'provider_service_mode': provider_service_mode,
        'selected_mode': selected_mode,
        'user_can_choose': user_can_choose,
        'available_provider_locations': available_provider_locations,
        'selected_provider_location': selected_provider_location,
        'provider_has_required_location': provider_has_required_location,
    }
    return render(request, 'services/detail.html', context)




def provider_profile(request, slug):
    """Perfil público de un proveedor"""
    provider_profile = get_object_or_404(ProviderProfile, slug=slug)
    provider = provider_profile.user
    
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

    # Meta tags
    meta_image = request.build_absolute_uri(provider_profile.profile_photo.url) if provider_profile.profile_photo else None
    provider_name = provider_profile.business_name or provider_profile.user.get_full_name()
    
    context = {
        'provider': provider,
        'provider_profile': provider_profile,
        'provider_name': provider_name,
        'meta_image': meta_image,
        'meta_title': f"{provider_profile.business_name or provider_profile.user.get_full_name()} | Liberi",
        'meta_description': (provider_profile.description[:160] if provider_profile.description else f"Proveedor de {provider_profile.category.name}"),
        'services': services,
        'reviews': reviews,
        'rating_avg': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'completed_bookings': completed_bookings,
    }
    return render(request, 'providers/profile.html', context)


@login_required
def set_current_zone(request):
    """Establecer zona actual (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    zone_id = request.POST.get('zone_id')
    
    if zone_id:
        try:
            zone = Zone.objects.get(id=zone_id, active=True)
            request.session['current_zone_id'] = zone.id
            
            return JsonResponse({
                'success': True,
                'zone_name': zone.name,
                'message': f'Zona establecida en {zone.name}'
            })
        except Zone.DoesNotExist:
            return JsonResponse({'error': 'Zona no encontrada'}, status=404)
    else:
        return JsonResponse({'error': 'Zona requerida'}, status=400)


@login_required
def detect_user_location(request):
    """Detectar ubicación del usuario basado en coordenadas (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')
    
    if not latitude or not longitude:
        return JsonResponse({'error': 'Coordenadas requeridas'}, status=400)
    
    try:
        lat = float(latitude)
        lng = float(longitude)
        
        # Aquí podrías implementar lógica para determinar la zona más cercana
        # Por ahora, simplemente guardamos las coordenadas en sesión
        request.session['user_latitude'] = lat
        request.session['user_longitude'] = lng
        
        return JsonResponse({
            'success': True,
            'message': 'Ubicación detectada'
        })
    except ValueError:
        return JsonResponse({'error': 'Coordenadas inválidas'}, status=400)


def landing_categories(request):
    """Landing page para compartir categorías en redes sociales"""
    return render(request, 'landings/categories.html')
