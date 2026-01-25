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
    Envía recordatorios (WhatsApp, Email, Push, DB) 1 hora antes del servicio.
    Se ejecuta cada 15 minutos vía Celery Beat.
    """
    from apps.notifications.utils import send_appointment_reminder_notification
    
    logger.info("🔔 Iniciando tarea de recordatorios multicanal...")
    
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
    
    processed_count = 0
    
    for booking in pending_reminders:
        try:
            logger.info(f"Processing reminder for booking {booking.id}")
            send_appointment_reminder_notification(booking)
            processed_count += 1
        except Exception as e:
            logger.error(f"❌ Error procesando recordatorio para booking {booking.id}: {e}", exc_info=True)
    
    logger.info(f"✅ Recordatorios procesados: {processed_count}")
    return {'processed': processed_count, 'total_pending': pending_reminders.count()}


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