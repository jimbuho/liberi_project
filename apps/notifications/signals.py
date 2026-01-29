from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.models import Booking, Payment, PaymentProof
from apps.notifications.utils import (
    send_new_service_request_notification,
    send_service_accepted_notification,
    send_reservation_paid_notification,
    send_payment_verified_notification,
    send_booking_rejected_notification
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
            
            # 3. Servicio Rechazado / Cancelado
            elif instance.status == 'cancelled':
                send_booking_rejected_notification(instance)
                
    except Exception as e:
        logger.error(f"Error in booking signal: {e}")

@receiver(post_save, sender=Payment)
def handle_payment_notification(sender, instance, created, **kwargs):
    """
    Maneja notificaciones de pagos
    """
    try:
        logger.info(f"🔔 Payment signal triggered: payment_id={instance.id}, status={instance.status}, created={created}")
        
        # Solo nos interesa cuando el pago se completa/verifica
        if instance.status == 'completed':
            logger.info(f"✅ Payment {instance.id} is completed - triggering notifications for booking {instance.booking.id}")
            # Esto cubre PayPhone instantáneo y validación manual
            # send_reservation_paid_notification debería manejar tanto cliente como proveedor
            send_reservation_paid_notification(instance.booking)
            logger.info(f"✅ Notifications sent for payment {instance.id}")
        else:
            logger.info(f"⏭️ Payment {instance.id} status is '{instance.status}' - skipping notifications")

    except Exception as e:
        logger.error(f"❌ Error in payment signal for payment {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender=PaymentProof)
def handle_payment_proof_verification(sender, instance, created, **kwargs):
    """
    Cuando un admin verifica un PaymentProof (comprobante de pago),
    crea un Payment con status='completed' y dispara las notificaciones
    """
    try:
        logger.info(f"🔔 PaymentProof signal: id={instance.id}, verified={instance.verified}, created={created}")
        
        # Solo actuar cuando está verificado
        if instance.verified:
            logger.info(f"✅ PaymentProof {instance.id} is verified - checking if Payment needs to be created")
            
            # Verificar si ya existe un Payment completado para esta reserva
            existing_payment = Payment.objects.filter(
                booking=instance.booking,
                status='completed'
            ).first()
            
            if existing_payment:
                logger.info(f"⏭️ Payment {existing_payment.id} already exists for booking {instance.booking.id} - skipping creation")
                # Asegurar que el booking esté marcado como paid
                if instance.booking.payment_status != 'paid':
                    logger.info(f"   Updating booking {instance.booking.id} payment_status to 'paid'")
                    instance.booking.payment_status = 'paid'
                    instance.booking.save()
                return
            
            # Crear el Payment
            from django.utils import timezone
            logger.info(f"💳 Creating Payment for booking {instance.booking.id}")
            payment = Payment.objects.create(
                booking=instance.booking,
                amount=instance.booking.total_cost,
                payment_method='bank_transfer',
                status='completed',
                transaction_id=f"BT-{instance.reference_code or instance.id}",
                reference_number=instance.reference_code,
                validated_by=instance.verified_by,
                validated_at=instance.verified_at or timezone.now(),
                notes=f"Pago verificado desde comprobante #{instance.id}"
            )
            
            # Actualizar el estado de pago de la reserva
            logger.info(f"📝 Updating booking {instance.booking.id} payment_status to 'paid'")
            instance.booking.payment_status = 'paid'
            instance.booking.save()
            
            logger.info(f"✅ Payment {payment.id} created and booking {instance.booking.id} updated to 'paid'")
            logger.info(f"   Payment signal will now trigger notifications automatically")
        else:
            logger.info(f"⏭️ PaymentProof {instance.id} is NOT verified - skipping")
            
    except Exception as e:
        logger.error(f"❌ Error in payment proof verification signal: {e}", exc_info=True)
