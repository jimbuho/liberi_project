from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Booking, Payment
from .tasks import send_whatsapp_message
import logging


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def booking_whatsapp_notifications(sender, instance, created, **kwargs):
    """
    Signal para enviar notificaciones de WhatsApp cuando cambia el estado de un Booking
    
    Flujo:
    1. Booking creado (created=True) → Notificar al proveedor
    2. Booking aceptado (status='accepted') → Notificar al cliente
    """
    # Obtener números de teléfono
    customer_phone = getattr(instance.customer.profile, 'phone', None)
    provider_phone = getattr(instance.provider.profile, 'phone', None)
    
    # CASO 1: Nuevo booking creado
    if created:
        if provider_phone:
            try:
                # Preparar variables para el template
                customer_name = instance.customer.get_full_name() or instance.customer.username
                service_name = instance.get_services_display()
                booking_date = instance.scheduled_time.strftime("%d/%m %H:%M")
                
                # Enviar mensaje al proveedor
                send_whatsapp_message.delay(
                    recipient=provider_phone,
                    template_name='booking_created',
                    variables=[customer_name, service_name, booking_date]
                )
                logger.info(f"📨 WhatsApp 'booking_created' encolado para proveedor {instance.provider.username}")
            except Exception as e:
                logger.error(f"❌ Error encolando WhatsApp para nuevo booking: {e}")
        else:
            logger.warning(f"⚠️ Proveedor {instance.provider.username} no tiene teléfono para WhatsApp")
        
        return  # Salir para no procesar los otros casos
    
    # CASO 2: Booking aceptado
    if instance.status == 'accepted' and customer_phone:
        try:
            # Verificar si acaba de cambiar a 'accepted' (no queremos enviar múltiples veces)
            # Usamos update_fields del kwargs si está disponible
            if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                provider_name = instance.provider.get_full_name() or instance.provider.username
                service_name = instance.get_services_display()
                
                send_whatsapp_message.delay(
                    recipient=customer_phone,
                    template_name='booking_accepted',
                    variables=[provider_name, service_name]
                )
                logger.info(f"📨 WhatsApp 'booking_accepted' encolado para cliente {instance.customer.username}")
        except Exception as e:
            logger.error(f"❌ Error encolando WhatsApp para booking aceptado: {e}")


@receiver(post_save, sender=Payment)
def payment_whatsapp_notification(sender, instance, created, **kwargs):
    """
    Signal para enviar notificación al proveedor cuando un pago es confirmado
    
    Solo se envía cuando el estado del pago cambia a 'completed'
    """
    # Solo actuar cuando el pago está completado
    if instance.status == 'completed':
        provider_phone = getattr(instance.booking.provider.profile, 'phone', None)
        
        if provider_phone:
            try:
                # Verificar si acaba de cambiar a 'completed'
                if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                    customer_name = instance.booking.customer.get_full_name() or instance.booking.customer.username
                    service_name = instance.booking.get_services_display()
                    
                    send_whatsapp_message.delay(
                        recipient=provider_phone,
                        template_name='payment_confirmed',
                        variables=[customer_name, service_name]
                    )
                    logger.info(f"📨 WhatsApp 'payment_confirmed' encolado para proveedor {instance.booking.provider.username}")
            except Exception as e:
                logger.error(f"❌ Error encolando WhatsApp para pago confirmado: {e}")
        else:
            logger.warning(f"⚠️ Proveedor {instance.booking.provider.username} no tiene teléfono para WhatsApp")