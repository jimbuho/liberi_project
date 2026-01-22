import logging
from apps.core.models import Notification
from apps.notifications.onesignal_service import OneSignalService

logger = logging.getLogger(__name__)

def send_new_service_request_notification(booking):
    """
    1. Solicitud de servicio. (Booking Created)
    Target: Provider
    """
    provider = booking.provider
    customer = booking.customer
    
    title = "Nueva Solicitud de Servicio"
    msg = f"{customer.get_full_name()} ha solicitado un servicio. ¡Revisa los detalles!"
    
    # DB Notification
    try:
        # Avoid duplicate if already created
        if not Notification.objects.filter(booking=booking, notification_type='booking_created').exists():
            Notification.objects.create(
                user=provider,
                title=title,
                message=msg,
                notification_type='booking_created',
                booking=booking,
                action_url=f"/provider/bookings/{booking.slug}/"
            )
    except Exception as e:
        logger.error(f"Error creating DB notification: {e}")

    # OneSignal
    try:
        target_url = f"/provider/bookings/{booking.slug}/"
        OneSignalService.send_to_user(provider, title, msg, url=target_url)
    except Exception as e:
        logger.error(f"OneSignal error: {e}")

def send_service_accepted_notification(booking):
    """
    2. Aceptacion de servicio. (Booking Accepted)
    Target: Customer
    """
    customer = booking.customer
    provider = booking.provider
    
    title = "¡Servicio Aceptado!"
    msg = f"Tu proveedor {provider.get_full_name()} ha aceptado la solicitud. Realiza el pago para confirmar."
    
    # DB
    try:
        Notification.objects.create(
            user=customer,
            title=title,
            message=msg,
            notification_type='booking_accepted',
            booking=booking,
            action_url=f"/bookings/{booking.slug}/pay/"
        )
    except Exception as e:
        logger.error(f"Error creating DB notification: {e}")

    # OneSignal
    try:
        target_url = f"/bookings/{booking.slug}/pay/"
        OneSignalService.send_to_user(customer, title, msg, url=target_url)
    except Exception as e:
        logger.error(f"OneSignal error: {e}")

def send_reservation_paid_notification(booking):
    """
    3. Reserva pagada. (Payment Verified)
    Target: Provider
    """
    provider = booking.provider
    customer = booking.customer
    
    title = "¡Pago Confirmado!"
    msg = f"El servicio para {customer.get_full_name()} está pagado. ¡Prepárate para la cita!"
    
    # DB Notification logic is primarily handled in Payment.send_payment_approved_notifications
    # We add this function to be called alongside or to handle OneSignal specifically.
    
    # OneSignal
    try:
        target_url = f"/provider/bookings/{booking.slug}/"
        OneSignalService.send_to_user(provider, title, msg, url=target_url)
    except Exception as e:
        logger.error(f"OneSignal error: {e}")

def send_appointment_reminder_notification(booking):
    """
    4. Recordatorio de cita.
    Target: Customer & Provider
    """
    customer = booking.customer
    provider = booking.provider
    
    # Format time safely
    time_str = booking.scheduled_time.strftime("%H:%M") if booking.scheduled_time else "N/A"
    
    # Customer
    try:
        title = "Recordatorio de Cita"
        msg = f"Tienes un servicio programado para las {time_str} con {provider.get_full_name()}."
        
        Notification.objects.create(
            user=customer, 
            title=title, 
            message=msg, 
            notification_type='system',
            booking=booking,
            action_url=f"/bookings/{booking.slug}/"
        )
        OneSignalService.send_to_user(customer, title, msg, url=f"/bookings/{booking.slug}/")
    except Exception as e:
        logger.error(f"Error sending customer reminder: {e}")

    # Provider
    try:
        title = "Recordatorio de Servicio"
        msg = f"Tienes un servicio programado para las {time_str} con {customer.get_full_name()}."
        
        Notification.objects.create(
            user=provider, 
            title=title, 
            message=msg, 
            notification_type='system',
            booking=booking,
            action_url=f"/provider/bookings/{booking.slug}/"
        )
        OneSignalService.send_to_user(provider, title, msg, url=f"/provider/bookings/{booking.slug}/")
    except Exception as e:
        logger.error(f"Error sending provider reminder: {e}")
