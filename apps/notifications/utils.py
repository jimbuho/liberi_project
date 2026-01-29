import logging
import sys
from django.db import transaction
from apps.core.models import Notification
from apps.notifications.onesignal_service import OneSignalService
from apps.core.tasks import (
    send_new_booking_to_provider_task,
    send_booking_accepted_to_customer_task,
    send_booking_rejected_to_customer_task,
    send_payment_approved_to_customer_task, 
    send_payment_approved_to_provider_task,
    send_appointment_reminder_email_task
)
from django.conf import settings

logger = logging.getLogger(__name__)

def _create_notification_if_not_exists(user, title, message, notif_type, booking, action_url):
    """Helper to create DB notification only if it doesn't duplicate recently (by type and user)"""
    logger.debug(
        f"Attempting to create Notification: user={user.id if user else 'None'}, type={notif_type}, booking={booking.id if booking else 'None'}"
    )
    if Notification.objects.filter(user=user, booking=booking, notification_type=notif_type).exists():
        logger.info(
            f"Duplicate Notification detected for user={user.id if user else 'None'}, type={notif_type}, booking={booking.id if booking else 'None'} – skipping creation."
        )
        return False
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notif_type,
        booking=booking,
        action_url=action_url,
    )
    logger.info(
        f"Notification created: user={user.id if user else 'None'}, type={notif_type}, booking={booking.id if booking else 'None'}"
    )
    return True

def _run_async_task(task, **kwargs):
    """Helper to run tasks on commit and skip in test/development mode"""
    # CRITICAL: Only run async tasks in production
    # In development/test, skip entirely to avoid Redis connection errors
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    
    logger.info(f"🔍 _run_async_task called: task={task.__name__}, environment={environment}")
    
    if environment != 'production':
        logger.info(f"✅ Skipping async task {task.__name__} in {environment} mode (emails only sent in production)")
        return
    
    logger.info(f"✅ Queueing async task {task.__name__} for production execution")
    
    def _do_run():
        try:
            task.delay(**kwargs)
        except Exception as e:
            logger.error(f"Error running async task {task.__name__}: {e}")

    transaction.on_commit(_do_run)

def send_new_service_request_notification(booking):
    """
    1. Solicitud de servicio. (Booking Created)
    Target: Provider
    Channels: DB, Push, Email
    """
    logger.info(f"🔔 send_new_service_request_notification called for booking {booking.id}")
    
    provider = booking.provider
    customer = booking.customer
    
    title = "Nueva Solicitud de Servicio"
    msg = f"{customer.get_full_name()} ha solicitado un servicio. ¡Revisa los detalles!"
    url = f"/bookings/{booking.id}/"
    
    # 1. DB Notification
    _create_notification_if_not_exists(provider, title, msg, 'booking_created', booking, url)

    # 2. Email - This will check environment and skip in development
    logger.info(f"📧 About to call _run_async_task for booking {booking.id}")
    _run_async_task(send_new_booking_to_provider_task, booking_id=str(booking.id))
    logger.info(f"✅ send_new_service_request_notification completed for booking {booking.id}")

def send_booking_rejected_notification(booking):
    """
    Notifica al cliente que la reserva fue rechazada.
    Target: Customer
    Channels: DB, Email
    """
    customer = booking.customer
    provider = booking.provider
    
    title = "Reserva No Confirmada"
    msg = f"Tu reserva con {provider.get_full_name()} ha sido cancelada o rechazada. Revisa los detalles."
    url = f"/bookings/{booking.id}/"
    
    _create_notification_if_not_exists(customer, title, msg, 'booking_cancelled', booking, url)
    
    _run_async_task(send_booking_rejected_to_customer_task, booking_id=str(booking.id))

def send_service_accepted_notification(booking):
    """
    2. Aceptacion de servicio. (Booking Accepted)
    Target: Customer
    Channels: DB, Email (Push & WhatsApp via signals)
    """
    customer = booking.customer
    provider = booking.provider
    
    title = "¡Servicio Aceptado!"
    msg = f"Tu proveedor {provider.get_full_name()} ha aceptado la solicitud. Realiza el pago para confirmar."
    url = f"/payments/{booking.id}/"
    
    _create_notification_if_not_exists(customer, title, msg, 'booking_accepted', booking, url)

    _run_async_task(send_booking_accepted_to_customer_task, booking_id=str(booking.id))

def send_reservation_paid_notification(booking):
    """
    3. Reserva pagada.
    Target: Customer & Provider
    Channels: DB, Email (Push & WhatsApp via signals)
    """
    logger.info(f"📧 send_reservation_paid_notification called for booking {booking.id}")
    
    provider = booking.provider
    customer = booking.customer
    payment = booking.payments.filter(status='completed').last()
    
    logger.info(f"   Provider: {provider.username}, Customer: {customer.username}, Payment: {payment.id if payment else 'None'}")
    
    # --- PROVEEDOR ---
    title_prov = "¡Pago Confirmado!"
    msg_prov = f"El servicio para {customer.get_full_name()} está pagado. ¡Prepárate para la cita!"
    url_prov = f"/bookings/{booking.id}/"

    logger.info(f"   Creating notification for PROVIDER: {provider.username}")
    _create_notification_if_not_exists(provider, title_prov, msg_prov, 'payment_verified', booking, url_prov)
            
    if payment:
        logger.info(f"   Queueing email task for provider")
        _run_async_task(send_payment_approved_to_provider_task, payment_id=payment.id)

    # --- CLIENTE ---
    title_cust = "Pago Exitoso"
    msg_cust = f"Tu pago ha sido procesado correctamente. ¡Tu cita está confirmada!"
    url_cust = f"/bookings/{booking.id}/"
    
    logger.info(f"   Creating notification for CUSTOMER: {customer.username}")
    _create_notification_if_not_exists(customer, title_cust, msg_cust, 'payment_verified', booking, url_cust)
            
    if payment:
        logger.info(f"   Queueing email task for customer")
        _run_async_task(send_payment_approved_to_customer_task, payment_id=payment.id)
    
    logger.info(f"✅ send_reservation_paid_notification completed for booking {booking.id}")

def send_payment_verified_notification(booking, payment):
    """
    Wrapper for manual payment verification
    """
    send_reservation_paid_notification(booking)

def send_appointment_reminder_notification(booking):
    """
    4. Recordatorio de cita.
    Target: Customer & Provider
    """
    customer = booking.customer
    provider = booking.provider
    
    time_str = booking.scheduled_time.strftime("%H:%M") if booking.scheduled_time else "N/A"
    
    # Customer
    title = "Recordatorio de Cita"
    msg = f"Tienes un servicio programado para las {time_str} con {provider.get_full_name()}."
    
    booking_url_cust = f"/bookings/{booking.id}/"
    
    if _create_notification_if_not_exists(customer, title, msg, 'system', booking, booking_url_cust):
        # Push
        try:
            OneSignalService.send_to_user(customer, title, msg, url=booking_url_cust)
        except Exception as e:
            logger.error(f"OneSignal error: {e}")
            
        # Email
        _run_async_task(send_appointment_reminder_email_task, booking_id=str(booking.id), target='customer')

        # WhatsApp (TWILIO_TEMPLATE_BOOKING_REMINDER)
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message

            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            full_booking_url_cust = f"{settings.BASE_URL}{booking_url_cust}"
            
            if hasattr(customer, 'profile') and customer.profile.phone:
                _run_async_task(
                     send_whatsapp_message,
                     phone=customer.profile.phone,
                     template_name='reminder',
                     variables=[service_name, time_str, full_booking_url_cust]
                )
        except Exception as e:
            logger.error(f"WhatsApp reminder error (customer): {e}")

    # Provider
    title_prov = "Recordatorio de Servicio"
    msg_prov = f"Tienes un servicio programado para las {time_str} con {customer.get_full_name()}."
    booking_url_prov = f"/bookings/{booking.id}/"
    
    if _create_notification_if_not_exists(provider, title_prov, msg_prov, 'system', booking, booking_url_prov):
        # Push
        try:
            OneSignalService.send_to_user(provider, title_prov, msg_prov, url=booking_url_prov)
        except Exception as e:
            logger.error(f"OneSignal error: {e}")
            
        # Email
        _run_async_task(send_appointment_reminder_email_task, booking_id=str(booking.id), target='provider')

        # WhatsApp
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message

            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            
            if hasattr(provider, 'profile') and provider.profile.phone:
                _run_async_task(
                     send_whatsapp_message,
                     phone=provider.profile.phone,
                     template_name='reminder',
                     variables=[service_name, time_str]
                )
        except Exception as e:
            logger.error(f"WhatsApp reminder error (provider): {e}")
