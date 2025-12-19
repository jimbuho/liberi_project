from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum, F
from django.http import JsonResponse
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from django.contrib.auth.models import User
from apps.core.models import (
    Profile, ProviderProfile, Service, Category, 
    Booking, Review, Location, ProviderLocation,
    AuditLog, ProviderSchedule, ProviderUnavailability,
    ProviderZoneCost, Zone, City, SystemConfig,
    WithdrawalRequest, BankAccount, ProviderBankAccount
)
from apps.core.image_upload import replace_image
from apps.core.utils import get_current_city
from apps.profiles.forms import ProviderLocationForm, ProviderProfileServiceModeForm

logger = logging.getLogger(__name__)

def get_active_categories():
    return Category.objects.all().order_by('name')

def get_active_balance(provider):
    """Calcula saldo activo solo de servicios COMPLETADOS por ambas partes"""
    
    qs = Booking.objects.filter(
        provider=provider, 
        status='completed',
        payment_status='paid',
        provider_completed_at__isnull=False,
        customer_completed_at__isnull=False,
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
    bookings = Booking.objects.filter(customer=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    completed_bookings = bookings.filter(status='completed').count()
    
    recent_bookings = bookings.order_by('-created_at')[:5]
    
    pending_reviews = bookings.filter(
        status='completed'
    ).exclude(
        id__in=Review.objects.values_list('booking_id', flat=True)
    )[:5]
    
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
    """Dashboard de proveedor - VERSIÓN SIMPLIFICADA UX"""
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('home')
    
    provider_profile = request.user.provider_profile
    
    # Estadísticas básicas
    bookings = Booking.objects.filter(provider=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    completed_bookings = bookings.filter(status='completed').count()
    
    # Ganancias totales
    total_earnings = bookings.filter(
        status='completed',
        payment_status='paid'
    ).aggregate(total=Sum('total_cost'))['total'] or 0
    
    # Saldo activo
    active_balance = get_active_balance(request.user)
    
    # NUEVO: Próximas reservas (48 horas)
    now = timezone.now()
    in_48_hours = now + timedelta(hours=48)
    
    upcoming_bookings = Booking.objects.filter(
        provider=request.user,
        status='accepted',
        payment_status='paid',
        scheduled_time__gte=now,
        scheduled_time__lte=in_48_hours
    ).select_related('customer', 'location').order_by('scheduled_time')[:5]
    
    # Servicios
    services = Service.objects.filter(provider=request.user)
    
    # Reviews recientes (solo 3)
    recent_reviews = Review.objects.filter(
        booking__provider=request.user
    ).select_related('customer', 'booking').order_by('-created_at')[:3]
    
    # Rating promedio
    rating_data = Review.objects.filter(
        booking__provider=request.user
    ).aggregate(
        avg_rating=Avg('rating'),
        total=Count('id')
    )
    
    # Verificar modalidad y ubicaciones
    has_service_mode = provider_profile.service_mode in ['home', 'local', 'both']
    has_base_location = ProviderLocation.objects.filter(provider=request.user, location_type='base').exists()
    has_local_locations = ProviderLocation.objects.filter(provider=request.user, location_type='local').exists()

    # --- ONBOARDING CHECKLIST LOGIC ---
    # 1. Subir documentos
    has_documents = bool(
        provider_profile.id_card_front and 
        provider_profile.id_card_back and 
        provider_profile.selfie_with_id
    )
    
    # 2. Subir primer servicio
    has_services = services.exists()
    
    # 3. Ser verificado
    is_verified = provider_profile.status == 'approved'
    is_processing = provider_profile.status in ['pending', 'resubmitted']
    is_rejected = provider_profile.status == 'rejected'
    
    verification_label = 'Verificación de perfil'
    if is_verified:
        verification_label = 'Perfil Verificado'
    elif is_processing:
        verification_label = 'Perfil en Verificación...'
    elif is_rejected:
        verification_label = 'Perfil Rechazado'
    
    # 4. Subir zonas de cobertura
    has_coverage_zones = provider_profile.coverage_zones.exists()
    
    # 5. Cargar costos de movilización
    has_zone_costs = ProviderZoneCost.objects.filter(provider=request.user).exists()
    
    # 6. Subir horarios
    has_schedules = ProviderSchedule.objects.filter(provider=request.user).exists()
    
    # Verificar si tiene perfil completo (nombre, categoría, descripción)
    has_profile = bool(
        provider_profile.business_name and
        provider_profile.description and
        provider_profile.category
    )
    
    # URL para el paso de servicios: si ya tiene servicios, editar el primero; si no, crear nuevo
    from django.urls import reverse
    first_service = services.first() if has_services else None
    if first_service:
        service_url = reverse('service_edit', args=[first_service.id])
    else:
        service_url = reverse('service_create')
    
    # Determinar si necesita cobertura según modalidad
    service_mode = provider_profile.service_mode
    needs_coverage = service_mode in ['home', 'both']
    
    # Construir steps base (comunes a todas las modalidades)
    raw_steps = [
        {'id': 0, 'label': 'Completar perfil', 'done': has_profile, 'url': reverse('provider_profile_edit')},
        {'id': 1, 'label': 'Subir documentos', 'done': has_documents, 'url': reverse('provider_register_step2')},
        {'id': 2, 'label': 'Crear primer servicio', 'done': has_services, 'url': service_url},
        {'id': 3, 'label': verification_label, 'done': is_verified, 'url': None,
         'is_processing': is_processing, 'is_rejected': is_rejected},
        {'id': 4, 'label': 'Seleccionar modalidad de atención', 'done': has_service_mode, 
         'url': reverse('provider_settings_service_mode')},
    ]
    
    # Agregar pasos condicionales SOLO si la modalidad lo requiere
    # Para "Solo en Local" (local): NO se agregan zonas ni costos
    # Para "A Domicilio" (home) o "Ambas" (both): SÍ se agregan zonas y costos
    step_id = 5
    if needs_coverage:
        raw_steps.extend([
            {'id': step_id, 'label': 'Definir zonas de cobertura', 'done': has_coverage_zones, 
             'url': reverse('provider_coverage_manage')},
            {'id': step_id + 1, 'label': 'Configurar costos de traslado', 'done': has_zone_costs, 
             'url': reverse('provider_zone_costs_manage')},
        ])
        step_id += 2
    
    # Paso final: horarios (SIEMPRE presente, independiente de la modalidad)
    raw_steps.append({
        'id': step_id, 
        'label': 'Configurar horarios', 
        'done': has_schedules, 
        'url': reverse('provider_schedule_manage')
    })

    onboarding_steps = []
    previous_step_done = True # El primer paso siempre está desbloqueado

    for step in raw_steps:
        # Si el perfil fue rechazado, habilitamos los pasos anteriores para edición
        if is_rejected and step['id'] <= 2:  # Permitir editar perfil, documentos y servicios
             step['status'] = 'completed_editable' # Nuevo estado para permitir edición
             step['locked'] = False
        elif step['done']:
            step['status'] = 'completed_editable' if step['id'] == 0 else 'completed'  # Perfil siempre editable
            step['locked'] = False
        elif previous_step_done:
            step['status'] = 'current'
            step['locked'] = False
        else:
            step['status'] = 'locked'
            step['locked'] = True
        
        onboarding_steps.append(step)
        # Para el paso de verificación, si está en proceso o rechazado, 
        # bloqueamos los siguientes pasos (previous_step_done = False)
        # pero el paso actual se muestra con su estado especial
        previous_step_done = step['done']
    
    completed_steps_count = sum(1 for step in onboarding_steps if step['done'])
    total_steps_count = len(onboarding_steps)
    onboarding_progress = int((completed_steps_count / total_steps_count) * 100)
    show_onboarding = completed_steps_count < total_steps_count
    
    # Parsear rejection_reasons si existe
    rejection_reasons_parsed = []
    if provider_profile.rejection_reasons:
        import json
        try:
            reasons_data = json.loads(provider_profile.rejection_reasons)
            if isinstance(reasons_data, list):
                for reason in reasons_data:
                    if isinstance(reason, dict):
                        rejection_reasons_parsed.append({
                            'code': reason.get('code', 'ERROR'),
                            'message': reason.get('message', 'Sin mensaje')
                        })
        except (json.JSONDecodeError, TypeError):
            # Si no es JSON válido, mostrar como texto plano
            rejection_reasons_parsed.append({
                'code': 'OBSERVACIÓN',
                'message': str(provider_profile.rejection_reasons)
            })
    
    # Calcular intentos restantes
    max_attempts = 3
    remaining_attempts = max(0, max_attempts - provider_profile.verification_attempts)
    
    context = {
        'provider_profile': provider_profile,
        'rejection_reasons_parsed': rejection_reasons_parsed,
        'remaining_attempts': remaining_attempts,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'completed_bookings': completed_bookings,
        'total_earnings': total_earnings,
        'active_balance': active_balance,
        'upcoming_bookings': upcoming_bookings,
        'services': services,
        'recent_reviews': recent_reviews,
        'rating_avg': round(rating_data['avg_rating'] or 0, 1),
        'total_reviews': rating_data['total'],
        'has_service_mode': has_service_mode,
        'has_base_location': has_base_location,
        'has_local_locations': has_local_locations,
        'onboarding_steps': onboarding_steps,
        'onboarding_progress': onboarding_progress,
        'show_onboarding': show_onboarding,
    }
    return render(request, 'dashboard/provider.html', context)


@login_required
def provider_settings(request):
    """
    Nueva página de configuración del proveedor con tabs.
    Consolida: Perfil, Ubicaciones, Disponibilidad, Pagos
    """
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder a esta página')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    
    # TAB 2: UBICACIONES
    base_location = ProviderLocation.objects.filter(
        provider=request.user, 
        location_type='base'
    ).first()
    
    local_locations = ProviderLocation.objects.filter(
        provider=request.user, 
        location_type='local'
    ).select_related('city', 'zone')
    
    coverage_zones = provider_profile.coverage_zones.all()
    
    zone_costs = ProviderZoneCost.objects.filter(
        provider=request.user
    ).select_related('zone')
    
    has_locations = base_location or local_locations.exists()
    
    # TAB 3: DISPONIBILIDAD
    schedules = ProviderSchedule.objects.filter(
        provider=request.user
    ).order_by('day_of_week', 'start_time')
    
    unavailabilities = ProviderUnavailability.objects.filter(
        provider=request.user,
        end_date__gte=timezone.now().date()
    ).order_by('start_date')[:5]
    
    # TAB 4: PAGOS
    bank_accounts = ProviderBankAccount.objects.filter(
        provider=request.user
    ).select_related('bank').order_by('-is_primary', 'created_at')
    
    recent_withdrawals = WithdrawalRequest.objects.filter(
        provider=request.user
    ).order_by('-created_at')[:5]
    
    # Agregar en provider_settings(), antes del context:
    services = Service.objects.filter(provider=request.user).order_by('-created_at')

    active_balance = get_active_balance(request.user)
    
    context = {
        'provider_profile': provider_profile,
        # Tab 2: Ubicaciones
        'base_location': base_location,
        'local_locations': local_locations,
        'coverage_zones': coverage_zones,
        'zone_costs': zone_costs,
        'has_locations': has_locations,
        # Tab 3: Disponibilidad
        'schedules': schedules,
        'unavailabilities': unavailabilities,
        # Tab 4: Pagos
        'bank_accounts': bank_accounts,
        'recent_withdrawals': recent_withdrawals,
        'active_balance': active_balance,
        'services': services,
    }
    return render(request, 'providers/settings.html', context)


@login_required
def provider_profile_edit(request):
    """Vista para editar el perfil del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden editar su perfil')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        
        business_name = request.POST.get('business_name')
        description = request.POST.get('description')
        category_id = request.POST.get('category')
        profile_photo = request.FILES.get('profile_photo')
        
        if email != request.user.email:
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, 'Este email ya está en uso por otro usuario')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
        
        if profile_photo:
            file_extension = profile_photo.name.split('.')[-1].lower()
            if file_extension not in ['jpg', 'jpeg', 'png']:
                messages.error(request, 'La foto debe ser JPG o PNG')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
            
            if profile_photo.size > 5 * 1024 * 1024:
                messages.error(request, 'La foto no puede superar los 5MB')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
        
        try:
            # Verificar si se está intentando cambiar la categoría en un perfil aprobado
            if provider_profile.status == 'approved' and category_id and str(provider_profile.category_id) != category_id:
                messages.error(request, '❌ No puedes cambiar la categoría de tu perfil una vez que ha sido aprobado.')
                return render(request, 'providers/profile_edit.html', {
                    'provider_profile': provider_profile,
                    'categories': get_active_categories(),
                })
            
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()
            
            request.user.profile.phone = phone
            request.user.profile.full_clean()
            request.user.profile.save()
            
            provider_profile.business_name = business_name
            provider_profile.description = description
            
            # Solo actualizar categoría si el perfil NO está aprobado
            if provider_profile.status != 'approved':
                provider_profile.category_id = category_id
            
            if profile_photo:
                photo_url = replace_image(
                    old_url=provider_profile.profile_photo,
                    new_file=profile_photo,
                    folder='profiles',
                    user_id=request.user.id
                )
                provider_profile.profile_photo = photo_url
            
            provider_profile.save()
            
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


@login_required
def provider_locations_list(request):
    """Lista todas las ubicaciones del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    if provider_profile.service_mode not in ['home', 'local', 'both']:
        messages.warning(request, '⚠️ Primero debes elegir tu modalidad de atención')
        return redirect('provider_settings_service_mode')
    
    locations = ProviderLocation.objects.filter(
        provider=request.user
    ).select_related('city', 'zone').order_by('location_type')
    
    base_location = locations.filter(location_type='base').first()
    local_locations = locations.filter(location_type='local')
    
    context = {
        'base_location': base_location,
        'local_locations': local_locations,
        'all_locations': locations,
        'service_mode': provider_profile.service_mode,
    }
    return render(request, 'providers/locations_list.html', context)


@login_required
def provider_location_create(request, loc_type=None):
    """Crear nueva ubicación con validaciones de modalidad"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    if provider_profile.service_mode not in ['home', 'local', 'both']:
        messages.warning(request, '⚠️ Primero debes elegir tu modalidad de atención')
        return redirect('provider_settings_service_mode')
    
    service_mode = provider_profile.service_mode
    
    if loc_type == 'base':
        if service_mode == 'local':
            messages.error(request, '❌ Tu modalidad "Solo en Local" no permite domicilio base.')
            return redirect('provider_locations_list')
        
        if ProviderLocation.objects.filter(provider=request.user, location_type='base').exists():
            messages.error(request, 'Ya tienes un domicilio base registrado')
            return redirect('provider_locations_list')
    
    elif loc_type == 'local':
        if service_mode == 'home':
            messages.error(request, '❌ Tu modalidad "Solo a Domicilio" no permite locales.')
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
            location.is_verified = True
            location.save()
            messages.success(request, f'✅ {location.label} creado exitosamente')
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
    """Configurar modalidad de atención"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo proveedores')
        return redirect('dashboard')
    
    provider_profile = request.user.provider_profile
    
    has_base = ProviderLocation.objects.filter(provider=request.user, location_type='base').exists()
    has_locals = ProviderLocation.objects.filter(provider=request.user, location_type='local').exists()
    
    if request.method == 'POST':
        form = ProviderProfileServiceModeForm(request.POST, instance=provider_profile)
        if form.is_valid():
            new_mode = form.cleaned_data['service_mode']
            
            if new_mode == 'home' and has_locals:
                messages.error(request, '❌ No puedes seleccionar "Solo a Domicilio" porque tienes locales registrados.')
                return redirect('provider_settings_service_mode')
            
            if new_mode == 'local' and has_base:
                messages.error(request, '❌ No puedes seleccionar "Solo en Local" porque tienes domicilio base registrado.')
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


@login_required
def provider_schedule_manage(request):
    """Gestión de horarios del proveedor"""
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden gestionar horarios')
        return redirect('dashboard')
    
    schedules = ProviderSchedule.objects.filter(
        provider=request.user
    ).order_by('day_of_week', 'start_time')
    
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
        
        if start_time >= end_time:
            messages.error(request, 'La hora de inicio debe ser menor que la hora de fin')
            return redirect('provider_schedule_manage')
        
        existing = ProviderSchedule.objects.filter(
            provider=request.user,
            day_of_week=day_of_week,
            start_time=start_time
        ).exists()
        
        if existing:
            messages.error(request, 'Ya tienes un horario para este día y hora')
            return redirect('provider_schedule_manage')
        
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
        
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if end < start:
            messages.error(request, 'La fecha de fin debe ser mayor o igual a la fecha de inicio')
            return redirect('provider_unavailability_manage')
        
        if start < timezone.now().date():
            messages.error(request, 'No puedes crear inactividades para fechas pasadas')
            return redirect('provider_unavailability_manage')
        
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
    
    coverage_zones = request.user.provider_profile.coverage_zones.all()
    
    zone_costs = ProviderZoneCost.objects.filter(
        provider=request.user
    ).select_related('zone')
    
    costs_dict = {zc.zone_id: zc for zc in zone_costs}
    
    zones_with_costs = []
    for zone in coverage_zones:
        zone_cost = costs_dict.get(zone.id)
        zones_with_costs.append({
            'zone': zone,
            'cost': zone_cost.travel_cost if zone_cost else None,
            'cost_id': zone_cost.id if zone_cost else None
        })
    
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
        
        max_cost = SystemConfig.get_config('max_travel_cost', 5)
        if cost > max_cost:
            messages.error(request, f'El costo no puede superar ${max_cost} USD')
            return redirect('provider_zone_costs_manage')
        
        if not request.user.provider_profile.coverage_zones.filter(id=zone_id).exists():
            messages.error(request, 'Esta zona no está en tu cobertura')
            return redirect('provider_zone_costs_manage')
        
        zone_cost, created = ProviderZoneCost.objects.update_or_create(
            provider=request.user,
            zone=zone,
            defaults={'travel_cost': cost}
        )
        
        action = 'configurado' if created else 'actualizado'
        messages.success(request, f'Costo de traslado {action} para {zone.name}')
        
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
    """Eliminar configuración de costo por zona"""
    if request.method != 'POST':
        return redirect('provider_zone_costs_manage')
    
    zone_cost = get_object_or_404(
        ProviderZoneCost,
        provider=request.user,
        zone_id=zone_id
    )
    
    zone_name = zone_cost.zone.name
    zone_cost.delete()
    
    messages.success(request, f'Configuración eliminada para {zone_name}.')
    
    return redirect('provider_zone_costs_manage')


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
    
    cities = City.objects.filter(active=True).order_by('display_order', 'name')
    
    current_zones = provider_profile.coverage_zones.all()
    current_zone_ids = set(current_zones.values_list('id', flat=True))
    
    covered_zones = current_zones
    
    selected_city_id = request.GET.get('city')
    selected_city = None
    available_zones = []
    
    if selected_city_id:
        try:
            selected_city_id = int(selected_city_id)
            selected_city = City.objects.get(id=selected_city_id, active=True)
            available_zones = Zone.objects.filter(
                city_id=selected_city_id, 
                active=True
            ).exclude(
                id__in=current_zone_ids
            ).order_by('name')
        except (ValueError, TypeError, City.DoesNotExist):
            selected_city_id = None
    
    context = {
        'provider_profile': provider_profile,
        'covered_zones': covered_zones,
        'available_zones': available_zones,
        'cities': cities,
        'selected_city_id': selected_city_id,
        'selected_city': selected_city,
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
        
        provider_profile.coverage_zones.add(zone)
        
        messages.success(request, f'Zona {zone.name} agregada a tu cobertura')
        
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
        
        if provider_profile.coverage_zones.count() <= 1:
            messages.error(request, 'Debes mantener al menos una zona de cobertura')
            return redirect('provider_coverage_manage')
        
        active_bookings = Booking.objects.filter(
            provider=request.user,
            location__zone=zone,
            status__in=['pending', 'accepted']
        ).count()
        
        if active_bookings > 0:
            messages.error(
                request,
                f'No puedes eliminar {zone.name} porque tienes {active_bookings} '
                f'reserva(s) activa(s) en esta zona.'
            )
            return redirect('provider_coverage_manage')
        
        provider_profile.coverage_zones.remove(zone)
        
        ProviderZoneCost.objects.filter(
            provider=request.user,
            zone=zone
        ).delete()
        
        messages.success(request, f'Zona {zone.name} removida de tu cobertura')
        
        AuditLog.objects.create(
            user=request.user,
            action='Zona removida de cobertura',
            metadata={'zone': zone.name}
        )
        
    except Exception as e:
        messages.error(request, f'Error al remover zona: {str(e)}')
    
    return redirect('provider_coverage_manage')