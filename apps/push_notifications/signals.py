from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from apps.core.models import Booking, Payment, Notification
from .tasks import send_push_notification
import logging


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def booking_push_notifications(sender, instance, created, **kwargs):
    """
    Envía notificaciones push cuando cambia el estado de un Booking
    
    Paralelo a whatsapp_notifications/signals.py
    """
    
    # CRITICAL: Skip entirely in non-production to avoid Redis connection errors
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    if environment != 'production':
        logger.info(f"⏭️ Skipping push notification signal in {environment} mode")
        return
    
    # ============================================
    # CASO 1: Nuevo booking creado → Notificar al proveedor
    # ============================================
    if created:
        try:
            customer_name = instance.customer.get_full_name() or instance.customer.username
            service_name = instance.get_services_display()
            booking_date = instance.scheduled_time.strftime("%d/%m %H:%M")
            booking_url = f"{settings.SITE_URL}/bookings/{instance.slug if instance.slug else instance.id}/"
            
            send_push_notification.delay(
                user_id=instance.provider.id,
                title="📋 Nueva Reserva",
                message=f"{customer_name} reservó {service_name} para el {booking_date}",
                notification_type="booking_created",
                url=booking_url,
                data={
                    'booking_id': str(instance.id),
                    'customer': customer_name,
                    'service': service_name,
                    'date': booking_date
                }
            )
            
            logger.info(
                f"📨 Push 'booking_created' encolado para proveedor "
                f"{instance.provider.username} (booking #{instance.id})"
            )
            
        except Exception as e:
            logger.error(
                f"❌ Error encolando Push 'booking_created' para "
                f"booking #{instance.id}: {e}",
                exc_info=True
            )
        
        return
    
    # ============================================
    # CASO 2: Booking aceptado → Notificar al cliente
    # ============================================
    if instance.status == 'accepted':
        try:
            # Verificar que realmente cambió a 'accepted'
            if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                
                provider_name = instance.provider.get_full_name() or instance.provider.username
                service_name = instance.get_services_display()
                booking_url = f"{settings.SITE_URL}/bookings/{instance.slug if instance.slug else instance.id}/"
                
                send_push_notification.delay(
                    user_id=instance.customer.id,
                    title="✅ Reserva Aceptada",
                    message=f"{provider_name} aceptó tu reserva de {service_name}. ¡No olvides pagar!",
                    notification_type="booking_accepted",
                    url=booking_url,
                    data={
                        'booking_id': str(instance.id),
                        'provider': provider_name,
                        'service': service_name
                    }
                )
                
                logger.info(
                    f"📨 Push 'booking_accepted' encolado para cliente "
                    f"{instance.customer.username} (booking #{instance.id})"
                )
                
        except Exception as e:
            logger.error(
                f"❌ Error encolando Push 'booking_accepted' para "
                f"booking #{instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Payment)
def payment_push_notification(sender, instance, created, **kwargs):
    """
    Envía notificación push al proveedor cuando un pago es confirmado
    """
    # CRITICAL: Skip entirely in non-production to avoid Redis connection errors
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    if environment != 'production':
        logger.info(f"⏭️ Skipping payment push notification signal in {environment} mode")
        return
    
    if instance.status == 'completed':
        try:
            # Verificar que acaba de cambiar a 'completed'
            if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                
                customer_name = (
                    instance.booking.customer.get_full_name() or 
                    instance.booking.customer.username
                )
                service_name = instance.booking.get_services_display()
                booking_url = f"{settings.SITE_URL}/bookings/{instance.booking.slug if instance.booking.slug else instance.booking.id}/"
                
                send_push_notification.delay(
                    user_id=instance.booking.provider.id,
                    title="💰 Pago Confirmado",
                    message=f"{customer_name} pagó ${instance.amount} por {service_name}",
                    notification_type="payment_confirmed",
                    url=booking_url,
                    data={
                        'booking_id': str(instance.booking.id),
                        'payment_id': str(instance.id),
                        'amount': str(instance.amount),
                        'customer': customer_name,
                        'service': service_name
                    }
                )
                
                logger.info(
                    f"📨 Push 'payment_confirmed' encolado para proveedor "
                    f"{instance.booking.provider.username} (payment #{instance.id})"
                )
                
        except Exception as e:
            logger.error(
                f"❌ Error encolando Push 'payment_confirmed' para "
                f"payment #{instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Notification)
def notification_push_mirror(sender, instance, created, **kwargs):
    """
    OPCIONAL: Envía push notification cada vez que se crea una Notification interna
    Esto garantiza que TODA notificación del sistema también llegue por push
    """
    if not created:
        return

    # Skip in non-production environments
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    if environment != 'production':
        logger.info(f"Non-production environment ({environment}): skipping Push mirror for Notification #{instance.id}")
        return
        
    if not getattr(settings, 'PUSH_NOTIFICATIONS_ENABLED', True):
        return
    
    def _send_push():
        try:
            # Mapear tipo de notificación interna a tipo push
            notification_type_map = {
                'booking_created': 'booking_created',
                'booking_accepted': 'booking_accepted',
                'booking_rejected': 'booking_rejected',
                'booking_cancelled': 'booking_cancelled',
                'booking_completed': 'booking_completed',
                'payment_received': 'payment_confirmed',
                'payment_verified': 'payment_confirmed',
                'system': 'system',
            }
            
            push_type = notification_type_map.get(
                instance.notification_type, 
                'general'
            )
            
            # URL de acción
            action_url = instance.action_url
            if action_url and not action_url.startswith('http'):
                action_url = f"{settings.SITE_URL}{action_url}"
            
            send_push_notification.delay(
                user_id=instance.user.id,
                title=instance.title,
                message=instance.message,
                notification_type=push_type,
                url=action_url,
                data={
                    'notification_id': str(instance.id),
                    'type': instance.notification_type
                }
            )
            
            logger.debug(
                f"📨 Push mirror encolado para Notification #{instance.id} "
                f"({instance.notification_type})"
            )
            
        except Exception as e:
            logger.error(
                f"❌ Error encolando Push mirror para Notification #{instance.id}: {e}"
            )
            
    # Run only after transaction commits
    from django.db import transaction
    transaction.on_commit(_send_push)
