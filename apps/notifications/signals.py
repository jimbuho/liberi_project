from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.models import Booking, Payment
from apps.notifications.utils import (
    send_new_service_request_notification,
    send_service_accepted_notification,
    send_reservation_paid_notification,
    send_payment_verified_notification
)
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def handle_booking_notification(sender, instance, created, **kwargs):
    """
    Maneja las notificaciones automáticas basadas en cambios de estado de la Reserva
    """
    try:
        # 1. Nueva Solicitud (Booking Created)
        if created and instance.status == 'pending':
            send_new_service_request_notification(instance)

        # Si no es creado, verificamos cambios de estado
        elif not created:
            # 2. Servicio Aceptado
            if instance.status == 'accepted' and instance.payment_status != 'paid':
                 # Usamos una verificación simple basada en la existencia de la notificación en DB para no repetir
                # send_service_accepted_notification maneja la lógica de no duplicar
                send_service_accepted_notification(instance)
                
    except Exception as e:
        logger.error(f"Error in booking signal: {e}")

@receiver(post_save, sender=Payment)
def handle_payment_notification(sender, instance, created, **kwargs):
    """
    Maneja notificaciones de pagos
    """
    try:
        # Solo nos interesa cuando el pago se completa/verifica
        if instance.status == 'completed':
            # Esto cubre PayPhone instantáneo y validación manual
            # send_reservation_paid_notification debería manejar tanto cliente como proveedor
            send_reservation_paid_notification(instance.booking)

    except Exception as e:
        logger.error(f"Error in payment signal: {e}")
