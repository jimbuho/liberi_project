import logging
from apps.core.models import Notification
from apps.notifications.onesignal_service import OneSignalService
from apps.core.tasks import (
    send_new_booking_to_provider_task,
    send_booking_accepted_to_customer_task,
    send_payment_approved_to_customer_task, 
    send_payment_approved_to_provider_task,
    send_appointment_reminder_email_task
)
from django.conf import settings

logger = logging.getLogger(__name__)

def _create_notification_if_not_exists(user, title, message, notif_type, booking, action_url):
    """Helper to create DB notification only if it doesn't duplicate recently (by type and user)"""
    if not Notification.objects.filter(user=user, booking=booking, notification_type=notif_type).exists():
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notif_type,
            booking=booking,
            action_url=action_url
        )
        return True
    return False

def send_new_service_request_notification(booking):
    """
    1. Solicitud de servicio. (Booking Created)
    Target: Provider
    Channels: DB, Push, Email
    """
    provider = booking.provider
    customer = booking.customer
    
    title = "Nueva Solicitud de Servicio"
    msg = f"{customer.get_full_name()} ha solicitado un servicio. ¡Revisa los detalles!"
    url = f"/provider/bookings/{booking.slug}/"
    
    # 1. DB Notification
    if _create_notification_if_not_exists(provider, title, msg, 'booking_created', booking, url):
        # 2. OneSignal
        try:
            OneSignalService.send_to_user(provider, title, msg, url=url)
        except Exception as e:
            logger.error(f"OneSignal error (booking_created): {e}")

        # 3. Email
        try:
            send_new_booking_to_provider_task.delay(booking_id=str(booking.id))
        except Exception as e:
            logger.error(f"Email error (booking_created): {e}")

        # 4. WhatsApp (TWILIO_TEMPLATE_BOOKING_CREATE)
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message
            
            # Prepare variables
            customer_name = customer.get_full_name() or customer.username
            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            date_str = booking.scheduled_time.strftime("%d/%m %H:%M")
            
            # Send to Provider
            if hasattr(provider, 'profile') and provider.profile.phone:
                send_whatsapp_message.delay(
                    phone=provider.profile.phone,
                    template_name='booking_created',
                    variables=[customer_name, service_name, date_str]
                )
        except Exception as e:
            logger.error(f"WhatsApp error (booking_created): {e}")

def send_service_accepted_notification(booking):
    """
    2. Aceptacion de servicio. (Booking Accepted)
    Target: Customer
    Channels: DB, Push, Email
    """
    customer = booking.customer
    provider = booking.provider
    
    title = "¡Servicio Aceptado!"
    msg = f"Tu proveedor {provider.get_full_name()} ha aceptado la solicitud. Realiza el pago para confirmar."
    url = f"/bookings/{booking.slug}/pay/"
    
    if _create_notification_if_not_exists(customer, title, msg, 'booking_accepted', booking, url):
        try:
            OneSignalService.send_to_user(customer, title, msg, url=url)
        except Exception as e:
            logger.error(f"OneSignal error (booking_accepted): {e}")

        try:
            send_booking_accepted_to_customer_task.delay(booking_id=str(booking.id))
        except Exception as e:
            logger.error(f"Email error (booking_accepted): {e}")

        # 4. WhatsApp (TWILIO_TEMPLATE_BOOKING_ACEPTED)
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message
            
            provider_name = provider.get_full_name() or provider.username
            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            booking_url = f"{settings.BASE_URL}/bookings/{booking.slug or str(booking.id)[:8]}/"

            if hasattr(customer, 'profile') and customer.profile.phone:
                send_whatsapp_message.delay(
                    phone=customer.profile.phone,
                    template_name='booking_accepted',
                    variables=[provider_name, service_name, booking_url]
                )
        except Exception as e:
             logger.error(f"WhatsApp error (booking_accepted): {e}")

def send_reservation_paid_notification(booking):
    """
    3. Reserva pagada.
    Target: Customer & Provider
    Channels: DB, Push, Email
    """
    provider = booking.provider
    customer = booking.customer
    payment = booking.payments.filter(status='completed').last()
    
    # --- PROVEEDOR ---
    title_prov = "¡Pago Confirmado!"
    msg_prov = f"El servicio para {customer.get_full_name()} está pagado. ¡Prepárate para la cita!"
    url_prov = f"/provider/bookings/{booking.slug}/"

    if _create_notification_if_not_exists(provider, title_prov, msg_prov, 'payment_verified', booking, url_prov):
        try:
            OneSignalService.send_to_user(provider, title_prov, msg_prov, url=url_prov)
        except Exception as e:
            logger.error(f"OneSignal error (payment_prov): {e}")
            
        try:
             if payment:
                 send_payment_approved_to_provider_task.delay(payment_id=payment.id)
        except Exception as e:
            logger.error(f"Email error (payment_prov): {e}")

    # --- CLIENTE ---
    title_cust = "Pago Exitoso"
    msg_cust = f"Tu pago ha sido procesado correctamente. ¡Tu cita está confirmada!"
    url_cust = f"/bookings/{booking.slug}/"
    
    if _create_notification_if_not_exists(customer, title_cust, msg_cust, 'payment_verified', booking, url_cust):
        try:
            OneSignalService.send_to_user(customer, title_cust, msg_cust, url=url_cust)
        except Exception as e:
            logger.error(f"OneSignal error (payment_cust): {e}")
            
        try:
            if payment:
                send_payment_approved_to_customer_task.delay(payment_id=payment.id)
        except Exception as e:
            logger.error(f"Email error (payment_cust): {e}")

        # 4. WhatsApp (TWILIO_TEMPLATE_BOOKING_CONFIRMED)
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message
            
            customer_name = customer.get_full_name() or customer.username
            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            
            # Provider Notification
            if hasattr(provider, 'profile') and provider.profile.phone:
                send_whatsapp_message.delay(
                    phone=provider.profile.phone,
                    template_name='payment_confirmed',
                    variables=[customer_name, service_name]
                )
        except Exception as e:
            logger.error(f"WhatsApp error (payment_prov): {e}")

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
    
    # Customer
    title = "Recordatorio de Cita"
    msg = f"Tienes un servicio programado para las {time_str} con {provider.get_full_name()}."
    
    booking_url_cust = f"/bookings/{booking.slug}/"
    
    if _create_notification_if_not_exists(customer, title, msg, 'system', booking, booking_url_cust):
        # Push
        try:
            OneSignalService.send_to_user(customer, title, msg, url=booking_url_cust)
        except Exception as e:
            logger.error(f"OneSignal error: {e}")
            
        # Email
        try:
             # We need to implement this task in core/tasks.py
             send_appointment_reminder_email_task.delay(booking_id=str(booking.id), target='customer')
        except Exception as e:
            logger.error(f"Email reminder error (customer): {e}")

        # WhatsApp (TWILIO_TEMPLATE_BOOKING_REMINDER)
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message

            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            full_booking_url_cust = f"{settings.BASE_URL}{booking_url_cust}"
            
            if hasattr(customer, 'profile') and customer.profile.phone:
                send_whatsapp_message.delay(
                     phone=customer.profile.phone,
                     template_name='reminder',
                     variables=[service_name, time_str, full_booking_url_cust]
                )
        except Exception as e:
            logger.error(f"WhatsApp reminder error (customer): {e}")

    # Provider
    title_prov = "Recordatorio de Servicio"
    msg_prov = f"Tienes un servicio programado para las {time_str} con {customer.get_full_name()}."
    booking_url_prov = f"/provider/bookings/{booking.slug}/"
    
    if _create_notification_if_not_exists(provider, title_prov, msg_prov, 'system', booking, booking_url_prov):
        # Push
        try:
            OneSignalService.send_to_user(provider, title_prov, msg_prov, url=booking_url_prov)
        except Exception as e:
            logger.error(f"OneSignal error: {e}")
            
        # Email
        try:
             send_appointment_reminder_email_task.delay(booking_id=str(booking.id), target='provider')
        except Exception as e:
            logger.error(f"Email reminder error (provider): {e}")

        # WhatsApp
        try:
            from apps.whatsapp_notifications.tasks import send_whatsapp_message

            service_name = booking.service_list[0].get('name', 'Servicio') if booking.service_list else 'Servicio'
            full_booking_url_prov = f"{settings.BASE_URL}{booking_url_prov}"
            
            if hasattr(provider, 'profile') and provider.profile.phone:
                send_whatsapp_message.delay(
                     phone=provider.profile.phone,
                     template_name='reminder',
                     variables=[service_name, time_str, full_booking_url_prov]
                )
        except Exception as e:
            logger.error(f"WhatsApp reminder error (provider): {e}")
