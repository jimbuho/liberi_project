from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from apps.core.email_utils import send_mail, run_task
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
try:
    import bleach
except ImportError:
    bleach = None  # Fallback stub if bleach is not installed

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


def sanitize_html(html_content):
    """
    Sanitiza HTML permitiendo solo tags y atributos seguros básicos.
    Permite: negrilla, cursiva, subrayado, párrafos, alineación, tamaños de fuente.
    """
    allowed_tags = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'span', 'div',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
    ]
    allowed_attrs = {
        '*': ['style'],
        'span': ['style'],
        'div': ['style'],
        'p': ['style'],
    }
    
    # Sanitizar el HTML (bleach 6.1.0 no soporta 'styles' parameter)
    # Solo permitimos tags y atributos básicos
    clean_html = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    
    return clean_html


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
# DASHBOARD VIEWS - MOVED TO apps/profiles/views.py
# ============================================================================
# dashboard(), dashboard_customer(), dashboard_provider() are now in profiles app


# ============================================================================
# BOOKING VIEWS - MOVED TO apps/bookings/views.py
# ============================================================================
# bookings_list(), booking_detail(), booking_create(), booking_accept(),
# booking_reject(), booking_complete() are now in bookings app


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
        available = request.POST.get('available') == 'on'
        
        # Obtener hasta 3 imágenes
        image_1 = request.FILES.get('image_1')
        image_2 = request.FILES.get('image_2')
        image_3 = request.FILES.get('image_3')
        
        try:
            # Sanitizar HTML en descripción
            clean_description = sanitize_html(description) if description else ''
            
            # Subir imágenes del servicio
            image_1_url = upload_service_image(file=image_1, provider_id=request.user.id) if image_1 else None
            image_2_url = upload_service_image(file=image_2, provider_id=request.user.id) if image_2 else None
            image_3_url = upload_service_image(file=image_3, provider_id=request.user.id) if image_3 else None
            
            # Crear servicio con las URLs
            service = Service.objects.create(
                provider=request.user,
                name=name,
                description=clean_description,
                base_price=base_price,
                duration_minutes=duration_minutes,
                image_1=image_1_url,
                image_2=image_2_url,
                image_3=image_3_url,
                available=available
            )
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Servicio creado',
                metadata={'service_id': service.id, 'name': name}
            )

            # Verificar si es el primer servicio
            provider_profile = request.user.provider_profile
            service_count = Service.objects.filter(provider=request.user).count()
            
            if service_count == 1:
                from apps.core.verification import trigger_validation_if_eligible
                
                triggered = trigger_validation_if_eligible(provider_profile)
                
                if triggered:
                    messages.success(
                        request, 
                        '✅ Servicio creado. Tu perfil ha entrado en proceso de verificación automática. '
                        'Te notificaremos por correo cuando el proceso finalice.'
                    )
                else:
                    if provider_profile.registration_step < 2:
                        messages.success(
                            request, 
                            f'✅ Servicio "{name}" creado. '
                            f'Por favor completa la verificación de identidad (subir cédula) para activar tu perfil.'
                        )
                    else:
                        messages.success(request, 'Servicio creado exitosamente')
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
        description = request.POST.get('description')
        service.description = sanitize_html(description) if description else ''
        service.base_price = request.POST.get('base_price')
        service.duration_minutes = request.POST.get('duration_minutes')
        service.available = request.POST.get('available') == 'on'
        
        # Manejar hasta 3 imágenes
        for i in range(1, 4):
            field_name = f'image_{i}'
            
            # Verificar si se debe eliminar la imagen
            if request.POST.get(f'remove_{field_name}') == 'true':
                setattr(service, field_name, None)
            # Verificar si se subió una nueva imagen
            elif request.FILES.get(field_name):
                try:
                    old_url = getattr(service, field_name)
                    new_image_url = replace_image(
                        old_url=old_url,
                        new_file=request.FILES[field_name],
                        folder='services',
                        user_id=request.user.id,
                        prefix='service'
                    )
                    setattr(service, field_name, new_image_url)
                except Exception as e:
                    messages.error(request, f'Error al actualizar imagen {i}: {str(e)}')
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

        # Eliminar imágenes asociadas
        for field_name in ['image_1', 'image_2', 'image_3']:
            image = getattr(service, field_name)
            if image:
                delete_image(image)
        
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

# ============================================================================
# PROVIDER SCHEDULE & AVAILABILITY - MOVED TO apps/profiles/views.py
# ============================================================================
# get_available_time_slots(), booking_create_step1(), provider_schedule_manage(),
# provider_schedule_create(), provider_schedule_delete(), provider_unavailability_*(),
# provider_toggle_active() are now in profiles/bookings apps


# ============================================================================
# PROVIDER COVERAGE & LOCATIONS - MOVED TO apps/profiles/views.py
# ============================================================================
# set_current_zone(), detect_user_location(), provider_coverage_manage(),
# provider_coverage_add(), provider_coverage_remove(), provider_location_delete(),
# provider_settings_service_mode() are now in profiles app

# Payment functions moved to apps/payments/views.py)

# ============================================================================
# PAYMENT VIEWS - MOVED TO apps/payments/views.py
# ============================================================================
# payment_bank_transfer(), payment_confirmation(), notify_admin_pending_payment(),
# send_payment_confirmation_email(), confirm_bank_transfer_payment() moved to payments app

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

# PAYMENT VIEWS - MOVED TO apps/payments/views.py
# ============================================================================
# payment_process(), payment_bank_transfer(), payment_confirmation(),
# confirm_bank_transfer_payment(), payphone_callback(), notify_admin_pending_payment(),
# send_payment_confirmation_email(), confirm_payphone_transaction() are now in payments app

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
# BOOKING COMPLETION & PROVIDER LOCATIONS - MOVED TO apps/bookings & apps/profiles
# ============================================================================
# booking_complete_with_code(), booking_report_incident() are now in bookings app
# provider_location_delete(), provider_settings_service_mode() are now in profiles app


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