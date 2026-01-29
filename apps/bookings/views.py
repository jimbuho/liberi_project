from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum, F
from django.conf import settings
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import UUID
import logging

from django.contrib.auth.models import User
from apps.core.models import (
    Booking, Service, Location, ProviderLocation, 
    Review, Notification, AuditLog, ProviderZoneCost,
    ProviderSchedule, ProviderUnavailability, SystemConfig
)
from apps.notifications.utils import (
    send_new_service_request_notification, 
    send_service_accepted_notification
)

logger = logging.getLogger(__name__)

def decimal_to_json(value):
    """Convierte Decimal a string para JSON"""
    return str(value) if isinstance(value, Decimal) else value

def get_available_time_slots(provider, service_date, service_duration_minutes, service_id=None):
    """
    Obtiene los horarios disponibles para un proveedor en una fecha específica.
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
        return []
    
    # Obtener horarios configurados para ese día
    schedules = ProviderSchedule.objects.filter(
        provider=provider,
        day_of_week=day_of_week,
        is_active=True
    )
    
    if not schedules.exists():
        return []
    
    # Solo contar reservas ACEPTADAS Y PAGADAS como bloqueadas
    existing_bookings = Booking.objects.filter(
        provider=provider,
        scheduled_time__date=service_date,
        status='accepted',
        payment_status='paid'
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
                booking_end = booking_start + timedelta(minutes=60) # Asumimos 1 hora por defecto si no hay duración? Ojo con esto.
                # En el código original usaba 60 minutos fijos para bloquear?
                # Revisando el código original: booking_end = booking_start + timedelta(minutes=60)
                # Parece que asume que las reservas existentes duran 60 minutos para el bloqueo.
                
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


@login_required
def bookings_list(request):
    """Lista de reservas del usuario (como cliente o proveedor)"""
    user = request.user
    
    # Obtener todas las reservas donde el usuario es cliente O proveedor
    bookings = Booking.objects.filter(
        Q(customer=user) | Q(provider=user)
    ).select_related('customer', 'provider', 'location').order_by('-created_at')
    
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
        UUID(str(booking_id))
        booking = get_object_or_404(Booking, id=booking_id)
    except ValueError:
        booking = get_object_or_404(Booking, slug=booking_id)
    
    # Verificar que el usuario tenga acceso
    is_customer = booking.customer == request.user
    is_provider = booking.provider == request.user
    
    if not is_customer and not is_provider:
        messages.error(request, 'No tienes acceso a esta reserva')
        return redirect('bookings_list')
    
    # LÓGICA DE CONTACTO - SIMPLIFICADA
    # Si el pago está completado, mostrar contacto inmediatamente
    can_contact = booking.payment_status == 'paid'
    contact_message = None
    
    if not can_contact:
        if is_customer:
            contact_message = 'Completa el pago para acceder a los datos de contacto del proveedor'
        else:
            contact_message = 'El contacto del cliente estará disponible una vez que el pago sea confirmado'
    
    # Generar código de finalización si es cliente y el pago está completado
    if is_customer and can_contact and not booking.completion_code:
        booking.generate_completion_code()
    
    show_completion_code = False
    if is_customer:
        show_completion_code = booking.should_show_completion_code()
    
    context = {
        'booking': booking,
        'can_contact': can_contact,
        'contact_message': contact_message,
        'show_completion_code': show_completion_code,
        'booking_location': booking.location,
        'booking_location_lat': float(booking.location.latitude) if booking.location else None,
        'booking_location_lng': float(booking.location.longitude) if booking.location else None,
        'is_customer': is_customer,
        'is_provider': is_provider,
    }
    return render(request, 'bookings/detail.html', context)


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
        
        has_schedule = ProviderSchedule.objects.filter(
            provider=provider,
            day_of_week=day_of_week,
            is_active=True
        ).exists()
        
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
def booking_create(request):
    """Crear una nueva reserva con validaciones mejoradas por zona"""
    
    if request.method != 'POST':
        return redirect('services_list') # TODO: check if services_list exists or needs to be imported/routed
    
    # Eliminado chequeo de rol para permitir que cualquier usuario cree reservas
    # if request.user.profile.role != 'customer':
    #     messages.error(request, 'Solo los clientes pueden hacer reservas')
    #     return redirect('services_list')
    
    service_id = request.POST.get('service_id')
    provider_id = request.POST.get('provider_id')
    location_id = request.POST.get('location_id')
    service_mode = request.POST.get('service_mode', 'home')
    provider_location_id = request.POST.get('provider_location_id')
    selected_date = request.POST.get('selected_date')
    selected_time = request.POST.get('selected_time')
    notes = request.POST.get('notes', '')
    
    service = get_object_or_404(Service, id=service_id)
    provider = get_object_or_404(User, id=provider_id)
    
    location = None
    if service_mode == 'home':
        if not location_id:
            messages.error(request, '⚠️ Por favor selecciona tu ubicación haciendo clic en la tarjeta correspondiente antes de confirmar la reserva.')
            return redirect('service_detail', service_code=service.service_code)
        location = get_object_or_404(Location, id=location_id, customer=request.user)
    
    provider_location = None
    if provider_location_id:
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
        if not provider_location:
            messages.error(request, 'Debe seleccionar un local del proveedor')
            return redirect('service_detail', service_code=service.service_code)
    
    try:
        scheduled_datetime = datetime.strptime(
            f"{selected_date} {selected_time}", 
            "%Y-%m-%d %H:%M"
        )
        scheduled_datetime = timezone.make_aware(scheduled_datetime)
    except ValueError:
        messages.error(request, 'Fecha u hora inválida')
        return redirect('service_detail', service_code=service.service_code)
    
    min_hours = SystemConfig.get_config('min_booking_hours', 1)
    now = timezone.now()
    if scheduled_datetime < now + timedelta(hours=min_hours):
        messages.error(
            request,
            f'La reserva debe ser al menos {min_hours} hora(s) en el futuro'
        )
        return redirect('service_detail', service_code=service.service_code)
    
    # Validar duplicados: Solo bloquear si tiene una reserva ACEPTADA pero NO PAGADA
    bookings_that_day = Booking.objects.filter(
        customer=request.user,
        provider=provider,
        scheduled_time__date=scheduled_datetime.date(),
        status='accepted',  # Solo aceptadas
        payment_status__in=['pending', 'pending_validation'] # Y pendiente de pago
    ).values_list('id', 'service_list')
    
    for booking_id, service_list in bookings_that_day:
        if service_list and isinstance(service_list, list):
            for service_item in service_list:
                item_service_id = service_item.get('service_id')
                if int(item_service_id) == int(service_id):
                    messages.error(
                        request, 
                        f'Ya tienes una reserva pendiente de pago para "{service.name}" el {scheduled_datetime.strftime("%d/%m")}. '
                        'Por favor realiza el pago de la reserva existente o espera a completarla.'
                    )
                    return redirect('service_detail', service_code=service.service_code)
    
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
    
    service_list = [{
        'service_id': service.id,
        'name': service.name,
        'price': decimal_to_json(service.base_price)
    }]
    
    sub_total_cost = Decimal(service.base_price)
    
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
        provider_location=provider_location,
        scheduled_time=scheduled_datetime,
        notes=notes,
        status='pending',
        payment_status='pending'
    )
    
    # La notificación se maneja vía signals (apps.notifications.signals)
    
    AuditLog.objects.create(
        user=request.user,
        action='Reserva creada',
        metadata={
            'booking_id': str(booking.id),
            'service_mode': service_mode,
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
    
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    if booking.status != 'pending':
        messages.error(request, 'Esta reserva ya no está pendiente')
        return redirect('booking_detail', booking_id=booking.id)
    
    booking.status = 'accepted'
    booking.save()

    # Notificaciones manejadas por signals

    
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
    
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('bookings_list')
    
    if booking.status != 'pending':
        messages.error(request, 'Esta reserva ya no está pendiente')
        return redirect('booking_detail', booking_id=booking.id)
    
    booking.status = 'cancelled'
    booking.save()
    
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
            
            # Notificaciones manejadas por signals

            
            AuditLog.objects.create(
                user=request.user,
                action='Reserva completada',
                metadata={'booking_id': str(booking.id)}
            )
        
        booking.save()
    
    return redirect('booking_detail', booking_id=booking.id)


@login_required
def booking_complete_with_code(request, booking_id):
    """
    Vista para que el proveedor complete el servicio ingresando el código
    """
    if request.method != 'POST':
        return redirect('booking_detail', booking_id=booking_id)
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    if booking.provider != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('booking_detail', booking_id=booking_id)
    
    if booking.status != 'accepted':
        messages.error(request, 'Esta reserva no está en estado aceptado')
        return redirect('booking_detail', booking_id=booking_id)
    
    if booking.payment_status != 'paid':
        messages.error(request, 'Esta reserva no ha sido pagada')
        return redirect('booking_detail', booking_id=booking_id)
    
    code = request.POST.get('completion_code', '').strip()
    
    if not code:
        messages.error(request, 'Debes ingresar el código de finalización')
        return redirect('booking_detail', booking_id=booking_id)
    
    if not booking.verify_completion_code(code):
        messages.error(request, 'Código incorrecto. Verifica con el cliente.')
        return redirect('booking_detail', booking_id=booking_id)
    
    try:
        with transaction.atomic():
            booking.status = 'completed'
            booking.provider_completed_at = timezone.now()
            booking.customer_completed_at = timezone.now()
            booking.save()
            
            # Notificaciones manejadas por signals

            
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
    
    if booking.customer != request.user:
        messages.error(request, 'No tienes permiso para esta acción')
        return redirect('booking_detail', booking_id=booking_id)
    
    if booking.incident_reported:
        messages.info(request, 'Ya has reportado una incidencia para esta reserva')
        return redirect('booking_detail', booking_id=booking.id)
    
    description = request.POST.get('incident_description', '').strip()
    
    if not description:
        messages.error(request, 'Debes describir qué sucedió')
        return redirect('booking_detail', booking_id=booking_id)
    
    try:
        with transaction.atomic():
            booking.incident_reported = True
            booking.incident_description = description
            booking.incident_reported_at = timezone.now()
            booking.save()
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='system',
                title='⚠️ Incidencia Reportada',
                message=f'El cliente {booking.customer.get_full_name()} reportó una incidencia: {description[:100]}',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
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
            
            AuditLog.objects.create(
                user=request.user,
                action='Incidencia reportada',
                metadata={'booking_id': str(booking.id)}
            )
            
            messages.success(request, 'Incidencia reportada. Un administrador revisará el caso.')
            
    except Exception as e:
        logger.error(f"Error reportando incidencia: {e}")
        messages.error(request, 'Error al reportar incidencia.')
    
    return redirect('booking_detail', booking_id=booking_id)
