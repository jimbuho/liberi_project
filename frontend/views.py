from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q, Avg, Count, Sum, F
from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import requests
import logging

from django.db import transaction

from core.models import (
    Profile, Category, Service, ProviderProfile, 
    Booking, Location, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability,
    PaymentMethod, BankAccount, PaymentProof,
    ProviderZoneCost, SystemConfig, Notification, Payment,
    WithdrawalRequest, ProviderBankAccount, Bank,
    EmailVerificationToken, City
)
from legal.models import LegalDocument, LegalAcceptance
from legal.views import get_client_ip, get_user_agent

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

# ============================================================================
# HOME & PUBLIC VIEWS
# ============================================================================

def home(request):
    """Página principal"""
    # NUEVO: Obtener y establecer ciudad actual
    current_city = get_current_city(request)
    if current_city:
        set_current_city(request, current_city)
    
    # ACTUALIZAR: Filtrar servicios por ciudad
    featured_services = Service.objects.filter(
        available=True, 
        provider__provider_profile__is_active=True,
        provider__provider_profile__status='approved',
        provider__provider_profile__coverage_zones__city=current_city
    ).distinct().order_by('-created_at')[:8]
    
    context = {
        'categories': get_active_categories(),
        'featured_services': featured_services,
        'current_city': current_city,  # NUEVO
        'cities': City.objects.filter(active=True).order_by('display_order'),  # NUEVO
    }
    return render(request, 'home.html', context)

def get_current_city(request):
    """Obtiene la ciudad actual del usuario o de sesión"""
    # 1. De perfil si está autenticado
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.current_city:
            return request.user.profile.current_city
    
    # 2. De sesión
    city_id = request.session.get('current_city_id')
    if city_id:
        try:
            return City.objects.get(id=city_id, active=True)
        except City.DoesNotExist:
            pass
    
    # 3. De ubicación más reciente del usuario
    if request.user.is_authenticated:
        last_location = Location.objects.filter(
            customer=request.user
        ).select_related('city').order_by('-created_at').first()
        
        if last_location and last_location.city:
            return last_location.city
    
    # 4. Por defecto, la primera ciudad activa
    return City.objects.filter(active=True).order_by('display_order').first()


def set_current_city(request, city):
    """Establece la ciudad actual en sesión y perfil"""
    request.session['current_city_id'] = city.id
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        request.user.profile.current_city = city
        request.user.profile.save(update_fields=['current_city'])

@login_required
def services_list(request):
    """Listado de servicios con filtros mejorados por ciudad y zona"""
    services = Service.objects.filter(available=True).select_related('provider')
    
    # NUEVO: Obtener ciudad actual
    current_city = get_current_city(request)
    
    # NUEVO: Cambiar ciudad si se solicita
    city_id = request.GET.get('city')
    if city_id:
        try:
            current_city = City.objects.get(id=city_id, active=True)
            set_current_city(request, current_city)
        except City.DoesNotExist:
            pass
    
    # NUEVO: Obtener zonas de la ciudad actual
    zones = Zone.objects.filter(
        active=True,
        city=current_city
    ).order_by('name') if current_city else Zone.objects.none()
    
    # Obtener zona actual
    current_zone_id = request.session.get('current_zone_id')
    current_zone = zones.filter(id=current_zone_id).first() if current_zone_id else None
    
    # Si no hay zona en sesión, intentar obtener de la última ubicación
    if not current_zone and current_city:
        last_location = request.user.locations.filter(
            city=current_city
        ).select_related('zone').order_by('-created_at').first()
        
        if last_location and last_location.zone:
            current_zone = last_location.zone
            request.session['current_zone_id'] = current_zone.id
    
    # Filtros
    category_id = request.GET.get('category')
    search = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    zone_id = request.GET.get('zone')
    
    # Si se selecciona una zona, guardarla en sesión
    if zone_id:
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
    
    # FILTRO SECUNDARIO: Por zona específica
    if current_zone:
        services = services.filter(
            provider__provider_profile__coverage_zones=current_zone,
            provider__provider_profile__is_active=True,
            provider__provider_profile__status='approved'
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
        
        # Costo de movilización según zona actual
        if current_zone:
            zone_cost = ProviderZoneCost.objects.filter(
                provider=service.provider,
                zone=current_zone
            ).first()
            
            if zone_cost:
                service.travel_cost = zone_cost.travel_cost
            else:
                # Usar costo por defecto del sistema
                service.travel_cost = SystemConfig.get_config('default_travel_cost', 2.50)
        else:
            service.travel_cost = service.provider.provider_profile.avg_travel_cost
    
    context = {
        'services': services,
        'categories': get_active_categories(),
        'zones': zones,
        'current_zone': current_zone,
        'current_city': current_city,  # NUEVO
        'cities': City.objects.filter(active=True).order_by('display_order'),  # NUEVO
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
    """Detalle de un servicio con validación de zona"""
    
    service = get_object_or_404(Service, service_code=service_code)
    
    # Obtener zona actual
    current_zone_id = request.session.get('current_zone_id')
    current_zone = Zone.objects.filter(id=current_zone_id).first() if current_zone_id else None
    
    # Verificar si el proveedor cubre la zona actual
    can_book = False
    zone_not_covered = False
    travel_cost = 0
    
    if current_zone:
        provider_covers_zone = service.provider.provider_profile.coverage_zones.filter(
            id=current_zone.id
        ).exists()
        
        if provider_covers_zone:
            can_book = True
            # Obtener costo específico para esta zona
            zone_cost = ProviderZoneCost.objects.filter(
                provider=service.provider,
                zone=current_zone
            ).first()
            
            if zone_cost:
                travel_cost = zone_cost.travel_cost
            else:
                travel_cost = Decimal(SystemConfig.get_config('default_travel_cost', 2.50))
        else:
            zone_not_covered = True
    else:
        # Si no hay zona seleccionada, usar costo promedio
        travel_cost = service.provider.provider_profile.avg_travel_cost
    
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
    
    # Ubicaciones del usuario que coincidan con zonas del proveedor
    user_locations = []
    valid_locations = []
    if request.user.is_authenticated:
        user_locations = Location.objects.filter(customer=request.user).select_related('zone')
        
        # Filtrar solo ubicaciones en zonas que el proveedor cubre
        provider_zone_ids = service.provider.provider_profile.coverage_zones.values_list('id', flat=True)
        valid_locations = [loc for loc in user_locations if loc.zone_id in provider_zone_ids]
    
    # Calcular costo total
    total_cost = service.base_price + Decimal(str(travel_cost))
    
    context = {
        'service': service,
        'reviews': reviews,
        'provider_rating': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'user_locations': user_locations,
        'valid_locations': valid_locations,
        'travel_cost': travel_cost,
        'total_cost': total_cost,
        'today': timezone.now().date(),
        'current_zone': current_zone,
        'can_book': can_book,
        'zone_not_covered': zone_not_covered,
    }
    return render(request, 'services/detail.html', context)

def providers_list(request):
    """Listado de proveedores"""
    providers = ProviderProfile.objects.filter(
        status='approved'
    ).select_related('user', 'category').prefetch_related('coverage_zones')
        
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
        'categories': get_active_categories(),
    }
    return render(request, 'providers/list.html', context)


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

@login_required
def provider_profile_edit(request):
    """
    Vista para editar el perfil del proveedor, incluyendo foto
    """
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden editar su perfil')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
        
    if request.method == 'POST':
        # Datos de usuario
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        
        # Datos de proveedor
        business_name = request.POST.get('business_name')
        description = request.POST.get('description')
        category_id = request.POST.get('category')
        profile_photo = request.FILES.get('profile_photo')
        
        # Validar email único (si cambió)
        if email != request.user.email:
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, 'Este email ya está en uso por otro usuario')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
        
        # Validar foto si se subió una nueva
        if profile_photo:
            # Validar tipo
            file_extension = profile_photo.name.split('.')[-1].lower()
            if file_extension not in ['jpg', 'jpeg', 'png']:
                messages.error(request, 'La foto debe ser JPG o PNG')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
            
            # Validar tamaño (5MB)
            if profile_photo.size > 5 * 1024 * 1024:
                messages.error(request, 'La foto no puede superar los 5MB')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
        
        try:
            # Actualizar usuario
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()
            
            # Actualizar perfil
            request.user.profile.phone = phone
            request.user.profile.full_clean()
            request.user.profile.save()
            
            # Actualizar perfil de proveedor
            provider_profile.business_name = business_name
            provider_profile.description = description
            provider_profile.category_id = category_id
            
            # Subir nueva foto si se proporcionó
            if profile_photo:
                photo_url = replace_image(
                    old_url=provider_profile.profile_photo,
                    new_file=profile_photo,
                    folder='profiles',
                    user_id=request.user.id
                )
                provider_profile.profile_photo = photo_url
            
            provider_profile.save()
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Perfil de proveedor actualizado',
                metadata={
                    'business_name': business_name,
                    'photo_updated': bool(profile_photo)
                }
            )
            
            messages.success(request, '¡Perfil actualizado exitosamente!')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar perfil: {str(e)}')
            return render(request, 'providers/profile_edit.html', {
                'provider_profile': provider_profile,
                'categories': get_active_categories(),
            })
    
    context = {
        'provider_profile': provider_profile,
        'categories': get_active_categories(),
    }
    return render(request, 'providers/profile_edit.html', context)


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
            # 🔥 VERIFICAR QUE EL EMAIL ESTÉ VERIFICADO
            if not user.profile.verified:
                messages.error(request, 'Credenciales inválidas o cuenta no verificada.')
                return render(request, 'auth/login.html')
            
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            messages.error(request, 'Credenciales inválidas.')
    
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
        terms_accepted = request.POST.get('terms_accepted')

        # Validaciones
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register.html')
        
        # NUEVA VALIDACIÓN
        if not terms_accepted:
            messages.error(request, 'Debes aceptar los Términos de Uso y Política de Privacidad')
            return render(request, 'auth/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'auth/register.html')
        
        try:
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Crear perfil
            profile = Profile(user=user, phone=phone, role='customer')
            profile.full_clean()  # Ejecuta las validaciones
            profile.save()
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')
            return render(request, 'auth/register.html')
        

        try:
            for doc_type in ['terms_user', 'privacy_user']:
                try:
                    document = LegalDocument.objects.get(
                        document_type=doc_type,
                        is_active=True,
                        status='published'
                    )
                    
                    LegalAcceptance.objects.get_or_create(
                        user=user,
                        document=document,
                        defaults={
                            'ip_address': get_client_ip(request),
                            'user_agent': get_user_agent(request),
                        }
                    )
                except LegalDocument.DoesNotExist:
                    pass
        except Exception as e:
            logger.warning(f"Error registrando aceptación legal: {e}")
        
        # 🔥 ENVIAR EMAIL EN SEGUNDO PLANO (NO BLOQUEA)
        from core.email_verification import send_verification_email
        success, message = send_verification_email(user, email)
        
        if not success:
            print(f"Email de verificación no se encendió para {email}: {message}")
            # No falles el registro, solo advierte
        
        # Crear entry de verificación para redirigir
        messages.success(
            request,
            '¡Registro exitoso! Te hemos enviado un email de verificación. '
            'Por favor, revisa tu bandeja de entrada.'
        )
        
        # Redirigir a página de espera de verificación
        return redirect('email_verification_pending_view')
    
    return render(request, 'auth/register.html')


def register_provider_view(request):
    """Registro de proveedor CON VERIFICACIÓN DE EMAIL"""
    if request.user.is_authenticated:
        messages.info(request, 'Ya tienes una sesión activa')
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        business_name = request.POST.get('business_name')
        profile_photo = request.FILES.get('profile_photo')
        terms_accepted = request.POST.get('terms_accepted')
        
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})

        # NUEVA VALIDACIÓN
        if terms_accepted is None or not terms_accepted:
            messages.error(request, 'Debes aceptar los Términos de Uso y Política de Privacidad')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})
        
        if not profile_photo:
            messages.error(request, 'La foto de perfil es obligatoria')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=False
            )

            photo_url = upload_profile_photo(
                file=profile_photo,
                user_id=user.id
            )
            
            # Crear perfil
            profile = Profile(user=user, phone=phone, role='provider')
            profile.full_clean()  # Ejecuta las validaciones
            profile.save()
            
            ProviderProfile.objects.create(
                user=user,
                category_id=category_id,
                description=description,
                business_name=business_name,
                profile_photo=photo_url,
                status='created',
                registration_step=1
            )

            try:
                for doc_type in ['terms_user', 'privacy_user']:
                    try:
                        document = LegalDocument.objects.get(
                            document_type=doc_type,
                            is_active=True,
                            status='published'
                        )
                        
                        LegalAcceptance.objects.get_or_create(
                            user=user,
                            document=document,
                            defaults={
                                'ip_address': get_client_ip(request),
                                'user_agent': get_user_agent(request),
                            }
                        )
                    except LegalDocument.DoesNotExist:
                        pass
            except Exception as e:
                logger.warning(f"Error registrando aceptación legal: {e}")
            
            success, message = send_verification_email(user, email)
            
            if success:
                messages.success(
                    request,
                    '¡Perfil creado! Te hemos enviado un email de verificación. '
                    'Completa la verificación para acceder a tu cuenta y continuar con la verificación de identidad.'
                )
                
                AuditLog.objects.create(
                    user=user,
                    action='Registro de proveedor iniciado - Esperando verificación de email',
                    metadata={
                        'email': email,
                        'business_name': business_name
                    }
                )
                
                return redirect('login')
            else:
                user.delete()
                messages.error(request, f'Error al enviar email: {message}')
                return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})

        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})
        except Exception as e:
            try:
                user = User.objects.get(username=username)
                user.delete()
            except:
                pass
            print(f'Error al crear perfil: {str(e)}')
            messages.error(request, f'Error al crear perfil: {str(e)}')
            return render(request, 'auth/register_provider.html', {'categories': get_active_categories()})

    context = {
        'categories': get_active_categories(),
    }
    return render(request, 'auth/register_provider.html', context)

@login_required
def provider_register_step2(request):
    """
    Segundo paso del registro de proveedor: Verificación de identidad
    """
    # Verificar que sea proveedor
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder a esta página')
        return redirect('home')
    
    # Verificar que tenga perfil de proveedor
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('home')
    
    provider_profile = request.user.provider_profile
    
    # Verificar que esté en el paso correcto
    if provider_profile.registration_step >= 2:
        messages.info(request, 'Ya completaste la verificación de identidad')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Obtener archivos
        id_card_front = request.FILES.get('id_card_front')
        id_card_back = request.FILES.get('id_card_back')
        selfie_with_id = request.FILES.get('selfie_with_id')
        
        # Validar que se subieron las 3 imágenes
        if not all([id_card_front, id_card_back, selfie_with_id]):
            messages.error(request, 'Debes subir las 3 imágenes requeridas')
            return render(request, 'auth/register_step2.html', {
                'provider_profile': provider_profile
            })
        
        # Validar tamaño de archivos
        for file in [id_card_front, id_card_back, selfie_with_id]:
            if file.size > 2 * 1024 * 1024:  # 2MB
                messages.error(request, f'La imagen {file.name} supera el tamaño máximo de 2MB')
                return render(request, 'auth/register_step2.html', {
                    'provider_profile': provider_profile
                })
        
        try:
            # Subir imágenes a Supabase/Storage
            from core.image_upload import upload_image
            
            front_url = upload_image(
                file=id_card_front,
                folder='documents/id_cards',
                user_id=request.user.id,
                prefix='front'
            )
            
            back_url = upload_image(
                file=id_card_back,
                folder='documents/id_cards',
                user_id=request.user.id,
                prefix='back'
            )
            
            selfie_url = upload_image(
                file=selfie_with_id,
                folder='documents/selfies',
                user_id=request.user.id,
                prefix='selfie'
            )
            
            # CORRECCIÓN: Actualizar perfil pero MANTENER status='created'
            provider_profile.id_card_front = front_url
            provider_profile.id_card_back = back_url
            provider_profile.selfie_with_id = selfie_url
            provider_profile.registration_step = 2
            provider_profile.status = 'created'  # Mantener en 'created', NO cambiar a 'pending'
            provider_profile.documents_verified = False  # Documentos aún no verificados
            provider_profile.save()
            
            # Log de auditoría
            AuditLog.objects.create(
                user=request.user,
                action='Documentos de identidad subidos',
                metadata={
                    'step': 2,
                    'status': 'created',
                    'next_step': 'create_first_service'
                }
            )
            
            # CORRECCIÓN: Mensaje indicando siguiente paso
            messages.success(
                request,
                '¡Documentos subidos exitosamente! '
                'Ahora crea tu primer servicio para solicitar la aprobación de tu perfil.'
            )
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error al subir documentos: {str(e)}')
            return render(request, 'auth/register_step2.html', {
                'provider_profile': provider_profile
            })
    
    context = {
        'provider_profile': provider_profile
    }
    return render(request, 'auth/register_step2.html', context)

def verify_email_view(request, token):
    """Verifica el email del usuario usando el token"""
    logger.info(f"Verificando email con token: {token}")
    
    try:
        verification_token = EmailVerificationToken.objects.get(token=token)
        print(f"Token encontrado en BD: {verification_token.token}")
        print(f"¿Es válido?: {verification_token.is_valid()}")
    except EmailVerificationToken.DoesNotExist:
        print(f"❌ Token NO encontrado en BD")
        messages.error(request, 'Token de verificación inválido o expirado')
        return redirect('home')
    
    # Validar que el token sea válido
    if not verification_token.is_valid():
        print(f"❌ Token expirado o ya verificado")
        messages.error(request, 'El token de verificación ha expirado')
        return redirect('home')
    
    # Verificar el token
    verification_token.verify()
    print(f"✅ Token verificado")
    
    # Activar usuario
    user = verification_token.user
    user.is_active = True
    user.save()
    
    # 🔥 MARCAR PERFIL COMO VERIFICADO
    user.profile.verified = True
    user.profile.save()
    print(f"✅ Perfil de {user.username} marcado como VERIFICADO")
    
    # Determinar si es proveedor
    is_provider = user.profile.role == 'provider'
    
    # Enviar email de bienvenida
    send_welcome_email(user, is_provider=is_provider)
    
    # Log
    AuditLog.objects.create(
        user=user,
        action='Email verificado',
        metadata={'email': user.email}
    )
    
    messages.success(
        request,
        '✓ Email verificado exitosamente. Tu cuenta está activa. Ya puedes iniciar sesión.'
    )
    
    return redirect('login')

def email_verification_pending(request):
    """Página que se muestra mientras se espera verificación"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Si el email ya está verificado, redirigir al dashboard
    if request.user.profile.verified:
        messages.success(request, '✅ Tu email ya ha sido verificado!')
        return redirect('dashboard')
    
    context = {
        'user_email': request.user.email,
    }
    return render(request, 'auth/email_verification_pending.html', context)

# Agregar esta vista a frontend/views.py

@login_required
def resend_verification_view(request):
    """Reenvía el email de verificación"""
    if request.method == 'POST':
        # Verificar que no esté ya verificado
        if request.user.profile.verified:
            messages.info(request, 'Tu email ya está verificado')
            return redirect('dashboard')
        
        # Reenviar email
        from core.email_verification import resend_verification_email
        success, message = resend_verification_email(request.user)
        
        if success:
            messages.success(
                request,
                '✓ Email de verificación reenviado. Revisa tu bandeja de entrada.'
            )
        else:
            messages.error(request, f'Error al reenviar: {message}')
        
        return redirect('email_verification_pending_view')
    
    return redirect('email_verification_pending_view')

@login_required
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
    booking = get_object_or_404(Booking, id=booking_id)
    
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
    
    # VALIDACIÓN CRÍTICA: Verificar que la zona de la ubicación esté en la cobertura del proveedor
    if not location.zone:
        messages.error(request, 'La ubicación seleccionada no tiene zona asignada')
        return redirect('service_detail', service_id=service.id)
    
    provider_covers_zone = provider.provider_profile.coverage_zones.filter(
        id=location.zone_id
    ).exists()
    
    if not provider_covers_zone:
        messages.error(
            request,
            f'El proveedor no cubre la zona {location.zone.name}. '
            'Por favor selecciona otra ubicación o busca otro proveedor.'
        )
        return redirect('service_detail', service_id=service.id)
    
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
    
    # Validar tiempo mínimo de anticipación (configurable)
    min_hours = SystemConfig.get_config('min_booking_hours', 1)
    now = timezone.now()
    if scheduled_datetime < now + timedelta(hours=min_hours):
        messages.error(
            request,
            f'La reserva debe ser al menos {min_hours} hora(s) en el futuro'
        )
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
    
    # Crear lista de servicios
    service_list = [{
        'service_id': service.id,
        'name': service.name,
        'price': decimal_to_json(service.base_price)
    }]
    
    sub_total_cost = Decimal(service.base_price)

    total_cost = sub_total_cost
    
    # Agregar costo de traslado según zona específica
    zone_cost = ProviderZoneCost.objects.filter(    
        provider=provider,
        zone=location.zone
    ).first()
    
    if zone_cost:
        travel_cost = Decimal(zone_cost.travel_cost)
    else:
        # Usar configuración por defecto
        travel_cost = Decimal(SystemConfig.get_config('default_travel_cost', 2.50))
    
    total_cost += travel_cost
    
    service = Decimal(settings.TAXES_ENDUSER_SERVICE_COMMISSION)
    iva = Decimal(settings.TAXES_IVA)
    tax = sub_total_cost * iva +  service * iva

    total_cost += tax
    
    # Crear reserva
    booking = Booking.objects.create(
        customer=request.user,
        provider=provider,
        service_list=service_list,
        sub_total_cost=sub_total_cost,
        service=service,
        tax=tax,
        total_cost=total_cost,
        travel_cost=travel_cost,
        location=location,
        scheduled_time=scheduled_datetime,
        notes=notes,
        status='pending',
        payment_status='pending'
    )

    # ============================================
    # CAMBIO #1: Crear notificación para proveedor
    # ============================================
    Notification.objects.create(
        user=provider,
        notification_type='booking_created',
        title='📋 Nueva Reserva Recibida',
        message=f'{request.user.get_full_name() or request.user.username} ha creado una nueva reserva para {scheduled_datetime.strftime("%d/%m/%Y %H:%M")}. Monto: ${total_cost}',
        booking=booking,
        action_url=f'/bookings/{booking.id}/'
    )

    # Enviar email al proveedor
    # Enviar email de forma asincrónica
    try:
        from core.tasks import send_new_booking_to_provider_task
        send_new_booking_to_provider_task.delay(booking_id=str(booking.id))
    except Exception as e:
        logger.error(f"Error enviando email al proveedor: {e}")
    
    # Log
    AuditLog.objects.create(
        user=request.user,
        action='Reserva creada',
        metadata={
            'booking_id': str(booking.id),
            'zone': location.zone.name,
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
            latitude=latitude,
            longitude=longitude
        )
        
        messages.success(request, 'Ubicación agregada exitosamente')
        
        # Redirigir a next o dashboard
        next_url = request.GET.get('next', 'dashboard')
        return redirect(next_url)
    
    context = {
        'zones': zones,
        'current_city': current_city,  # NUEVO
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

def get_available_time_slots(provider, service_date, service_duration_minutes):
    """
    Obtiene los horarios disponibles para un proveedor en una fecha específica
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
        # CORRECCIÓN: Crear slots AWARE en lugar de NAIVE
        current_time = datetime.combine(service_date, schedule.start_time)
        end_time = datetime.combine(service_date, schedule.end_time)
        
        # Hacer los datetimes "aware" con el timezone configurado
        current_time = timezone.make_aware(current_time)
        end_time = timezone.make_aware(end_time)
        
        while current_time + timedelta(minutes=service_duration_minutes) <= end_time:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=service_duration_minutes)
            
            # Verificar si este slot está ocupado
            is_occupied = False
            for booking in existing_bookings:
                booking_start = booking.scheduled_time
                booking_end = booking_start + timedelta(minutes=60)  # Estimado
                
                # AHORA AMBOS SON AWARE - la comparación funcionará
                if (slot_start < booking_end and slot_end > booking_start):
                    is_occupied = True
                    break
            
            if not is_occupied:
                # Verificar que sea al menos 1 hora en el futuro
                now = timezone.now()
                if slot_start > now + timedelta(hours=1):
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
    
    # Todas las zonas disponibles
    all_zones = Zone.objects.filter(active=True).order_by('city', 'name')
    
    # Zonas actuales del proveedor
    current_zones = provider_profile.coverage_zones.all()
    current_zone_ids = set(current_zones.values_list('id', flat=True))
    
    # Separar zonas cubiertas y disponibles
    covered_zones = current_zones
    available_zones = [z for z in all_zones if z.id not in current_zone_ids]
    
    context = {
        'provider_profile': provider_profile,
        'covered_zones': covered_zones,
        'available_zones': available_zones,
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
        
        messages.success(request, f'Zona {zone.name} agregada a tu cobertura')
        
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
        
        # Verificar que no sea la única zona
        if provider_profile.coverage_zones.count() <= 1:
            messages.error(request, 'Debes mantener al menos una zona de cobertura')
            return redirect('provider_coverage_manage')
        
        # Verificar que no tenga reservas activas en esta zona
        active_bookings = Booking.objects.filter(
            provider=request.user,
            location__zone=zone,
            status__in=['pending', 'accepted']
        ).count()
        
        if active_bookings > 0:
            messages.error(
                request,
                f'No puedes eliminar {zone.name} porque tienes {active_bookings} '
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
        
        messages.success(
            request,
            f'Zona {zone.name} removida de tu cobertura'
        )
        
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
    banks = Bank.objects.filter(is_active=True).order_by('name')
    
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