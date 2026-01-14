from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from apps.core.models import Booking, Payment
from .tasks import send_whatsapp_message
import logging


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def booking_whatsapp_notifications(sender, instance, created, **kwargs):
    """
    Signal para enviar notificaciones de WhatsApp cuando cambia el estado de un Booking.
    
    Flujo:
    1. Booking creado (created=True) → Notificar al proveedor
    2. Booking aceptado (status='accepted') → Notificar al cliente
    """
    # Obtener números de teléfono
    customers_profile = getattr(instance.customer, 'profile', None)
    customer_phone = getattr(customers_profile, 'phone', None) if customers_profile else None
    
    # Usar el método del modelo para obtener el teléfono correcto (considera ubicación)
    provider_phone = instance.get_notification_whatsapp()
    
    # ============================================
    # CASO 1: Nuevo booking creado
    # ============================================
    if created:
        if provider_phone:
            try:
                customer_name = instance.customer.get_full_name() or instance.customer.username
                service_name = instance.get_services_display()
                booking_date = instance.scheduled_time.strftime("%d/%m %H:%M")
                booking_identifier = getattr(instance, 'slug', instance.id)
                
                send_whatsapp_message.delay(
                    recipient=provider_phone,
                    template_name='booking_created',
                    variables=[
                        customer_name,
                        service_name,
                        booking_date,
                        booking_identifier
                    ]
                )
                
                logger.info(
                    f"📨 WhatsApp 'booking_created' encolado para proveedor "
                    f"{instance.provider.username} al número {provider_phone} (booking #{instance.id})"
                )
                
            except Exception as e:
                logger.error(
                    f"❌ Error encolando WhatsApp 'booking_created' para "
                    f"booking #{instance.id}: {e}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"⚠️ Proveedor {instance.provider.username} no tiene teléfono "
                f"registrado (ni en perfil ni en ubicación) para booking #{instance.id}"
            )
        
        return
    
    # ============================================
    # CASO 2: Booking aceptado
    # ============================================
    if instance.status == 'accepted' and customer_phone:
        try:
            if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                
                provider_name = instance.provider.get_full_name() or instance.provider.username
                service_name = instance.get_services_display()
                booking_identifier = getattr(instance, 'slug', instance.id)
                
                send_whatsapp_message.delay(
                    recipient=customer_phone,
                    template_name='booking_accepted',
                    variables=[
                        provider_name,
                        service_name,
                        booking_identifier
                    ]
                )
                
                logger.info(
                    f"📨 WhatsApp 'booking_accepted' encolado para cliente "
                    f"{instance.customer.username} (booking #{instance.id})"
                )
                
        except Exception as e:
            logger.error(
                f"❌ Error encolando WhatsApp 'booking_accepted' para "
                f"booking #{instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Payment)
def payment_whatsapp_notification(sender, instance, created, **kwargs):
    """
    Signal para enviar notificación al proveedor cuando un pago es confirmado.
    
    Solo se envía cuando el estado del pago cambia a 'completed'.
    """
    # Solo actuar cuando el pago está completado
    if instance.status == 'completed':
        provider_phone = getattr(instance.booking.provider.profile, 'phone', None)
        
        if provider_phone:
            try:
                # Verificar si acaba de cambiar a 'completed'
                if kwargs.get('update_fields') is None or 'status' in kwargs.get('update_fields', []):
                    
                    # Preparar datos
                    customer_name = (
                        instance.booking.customer.get_full_name() or 
                        instance.booking.customer.username
                    )
                    service_name = instance.booking.get_services_display()
                    
                    # Enviar WhatsApp al proveedor con 2 variables
                    # Este template NO tiene botón dinámico (usa botón estático a /provider/earnings)
                    send_whatsapp_message.delay(
                        recipient=provider_phone,
                        template_name='payment_confirmed',
                        variables=[
                            customer_name,  # {{1}} - Nombre del cliente
                            service_name    # {{2}} - Servicio
                        ]
                    )
                    
                    logger.info(
                        f"📨 WhatsApp 'payment_confirmed' encolado para proveedor "
                        f"{instance.booking.provider.username} (payment #{instance.id})"
                    )
                    
            except Exception as e:
                logger.error(
                    f"❌ Error encolando WhatsApp 'payment_confirmed' para "
                    f"payment #{instance.id}: {e}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"⚠️ Proveedor {instance.booking.provider.username} no tiene teléfono "
                f"registrado para notificación de pago #{instance.id}"
            )