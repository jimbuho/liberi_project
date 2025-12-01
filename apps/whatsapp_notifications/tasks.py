from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================
# IMPORTS DE MODELOS
# ============================================
from apps.core.models import Booking
from apps.whatsapp_notifications.services import WhatsAppService


# ============================================
# TAREA: Enviar recordatorios WhatsApp
# ============================================

@shared_task
def send_service_reminders():
    """
    Envía recordatorios WhatsApp 1 hora antes del servicio.
    Se ejecuta cada 15 minutos vía Celery Beat.
    
    IMPORTANTE: Incluye 3 variables para el template 'reminder':
    1. Nombre del servicio
    2. Hora del servicio
    3. URL del booking
    """
    logger.info("🔔 Iniciando tarea de recordatorios WhatsApp...")
    
    now = timezone.now()
    time_window_start = now + timedelta(minutes=45)
    time_window_end = now + timedelta(minutes=75)
    
    logger.info(f"⏰ Ventana de búsqueda: {time_window_start} a {time_window_end}")
    
    # Obtener reservas que necesitan recordatorio
    pending_reminders = Booking.objects.filter(
        scheduled_time__gte=time_window_start,
        scheduled_time__lte=time_window_end,
        status='accepted',
        payment_status='paid'
    ).select_related('customer', 'provider', 'location')
    
    logger.info(f"📋 Reservas encontradas: {pending_reminders.count()}")
    
    sent_count = 0
    
    for booking in pending_reminders:
        try:
            # ============================================
            # DATOS DEL BOOKING
            # ============================================
            customer_phone = booking.customer.profile.phone
            provider_phone = booking.provider.profile.phone
            
            # Nombre del servicio
            if booking.service_list and len(booking.service_list) > 0:
                service_name = booking.service_list[0].get('name', 'Servicio')
            else:
                service_name = 'Servicio'
            
            # Hora formateada
            scheduled_time = booking.scheduled_time
            time_str = scheduled_time.strftime("%H:%M")
            
            # IMPORTANTE: URL del booking (3era variable)
            booking_identifier = booking.slug if booking.slug else str(booking.id)[:8]
            
            logger.info(f"📅 Booking {booking.id}: {service_name} a las {time_str}")
            
            # ============================================
            # RECORDATORIO PARA EL CLIENTE
            # ============================================
            if customer_phone:
                logger.info(f"📱 Enviando recordatorio a cliente: {customer_phone}")
                try:
                    send_whatsapp_message.delay(
                        phone=customer_phone,
                        template_type='reminder',
                        variables=[service_name, time_str, booking_identifier]
                    )
                    logger.info(f"✅ Recordatorio cliente encolado")
                    sent_count += 1
                except Exception as e:
                    logger.error(f"❌ Error con recordatorio a cliente: {e}")
            else:
                logger.warning(f"⚠️ Cliente sin teléfono")
            
            # ============================================
            # RECORDATORIO PARA EL PROVEEDOR
            # ============================================
            if provider_phone:
                logger.info(f"📱 Enviando recordatorio a proveedor: {provider_phone}")
                try:
                    send_whatsapp_message.delay(
                        phone=provider_phone,
                        template_type='reminder',
                        variables=[service_name, time_str, booking_identifier]
                    )
                    logger.info(f"✅ Recordatorio proveedor encolado")
                    sent_count += 1
                except Exception as e:
                    logger.error(f"❌ Error con recordatorio a proveedor: {e}")
            else:
                logger.warning(f"⚠️ Proveedor sin teléfono")
                
        except Exception as e:
            logger.error(f"❌ Error procesando booking {booking.id}: {e}", exc_info=True)
    
    logger.info(f"✅ Recordatorios encolados: {sent_count}")
    return {'sent': sent_count, 'total_pending': pending_reminders.count()}


# ============================================
# TAREA: Enviar mensaje WhatsApp genérico
# ============================================

@shared_task
def send_whatsapp_message(phone=None, template_type=None, variables=None, 
                         recipient=None, template_name=None):
    """
    Envía un mensaje WhatsApp usando un template.
    
    FLEXIBLE: Acepta múltiples nombres de parámetros para compatibilidad:
    - phone o recipient (número de teléfono)
    - template_type o template_name (tipo de template)
    
    Formas de llamada soportadas:
    1. send_whatsapp_message(phone='...', template_type='reminder', variables=[...])
    2. send_whatsapp_message(recipient='...', template_name='reminder', variables=[...])
    3. send_whatsapp_message(phone='...', template_name='reminder', variables=[...])
    """
    # Normalizar parámetros
    phone_number = phone or recipient
    template = template_type or template_name
    
    if not phone_number or not template:
        logger.error(f"❌ Parámetros incompletos: phone={phone_number}, template={template}")
        return {'success': False, 'error': 'Parámetros requeridos: phone/recipient y template_type/template_name'}
    
    logger.info(f"📱 Enviando WhatsApp '{template}' a {phone_number}")
    
    try:
        # Llamar al servicio con los nombres CORRECTOS esperados por services.py
        whatsapp_service = WhatsAppService()
        result = whatsapp_service.send_message(
            recipient_number=phone_number,
            template_name=template,
            variables=variables or []
        )
        
        logger.info(f"✅ WhatsApp enviado exitosamente (Log ID: {result.id})")
        return {
            'success': True,
            'status': 'sent',
            'log_id': result.id,
            'message_id': result.message_id if hasattr(result, 'message_id') else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error al enviar WhatsApp: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


# ============================================
# TAREA: Reintentar mensajes fallidos
# ============================================

@shared_task
def retry_failed_messages():
    """
    Reintenta enviar mensajes que fallaron usando variables guardadas.
    """
    from apps.whatsapp_notifications.models import WhatsAppLog
    
    logger.info("🔄 Reintentando mensajes fallidos...")
    
    failed_logs = WhatsAppLog.objects.filter(
        status='failed',
        template_variables__isnull=False
    )[:10]
    
    logger.info(f"📋 Mensajes para reintentar: {failed_logs.count()}")
    
    retried_count = 0
    
    for log in failed_logs:
        try:
            logger.info(f"🔄 Reintentando Log {log.id}: {log.message_type} → {log.recipient}")
            
            send_whatsapp_message.delay(
                phone=log.recipient,
                template_type=log.message_type,
                variables=log.template_variables
            )
            
            retried_count += 1
            
        except Exception as e:
            logger.error(f"❌ Error reintentando Log {log.id}: {e}")
    
    logger.info(f"✅ {retried_count} mensaje(s) encolado(s) para reintento")
    return {'retried': retried_count}