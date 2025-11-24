from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)

# ============================================
# IMPORTS DE MODELOS
# ============================================
from core.models import Booking
from whatsapp_notifications.models import WhatsAppLog
from whatsapp_notifications.services import WhatsAppService


# ============================================
# TAREA: Enviar recordatorios WhatsApp
# ============================================

@shared_task
def send_service_reminders():
    """
    Envía recordatorios WhatsApp 1 hora antes del servicio
    Se ejecuta cada 15 minutos vía Celery Beat
    CORREGIDO: Ahora incluye la URL de booking como tercera variable
    """
    logger.info("🔔 Iniciando tarea de recordatorios WhatsApp...")
    
    now = timezone.now()
    # Buscar servicios en los próximos 15 minutos a 1 hora 15 minutos
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
            # Obtener datos
            customer_phone = booking.customer.profile.phone
            provider_phone = booking.provider.profile.phone
            
            # Obtener nombre del servicio
            if booking.service_list and len(booking.service_list) > 0:
                service_name = booking.service_list[0].get('name', 'Servicio')
            else:
                service_name = 'Servicio'
            
            # Obtener hora formateada
            scheduled_time = booking.scheduled_time
            time_str = scheduled_time.strftime("%H:%M")
            
            # CORREGIDO: Construir URL de booking
            booking_identifier = booking.slug if booking.slug else str(booking.id)[:8]
            booking_url = f"{settings.BASE_URL}/bookings/{booking_identifier}/"
            
            logger.info(f"🔗 URL de booking: {booking_url}")
            
            whatsapp_service = WhatsAppService()
            
            # ============================================
            # RECORDATORIO PARA EL CLIENTE
            # ============================================
            logger.info(f"📱 Enviando recordatorio a cliente: {customer_phone}")
            
            try:
                whatsapp_service.send_message(
                    phone=customer_phone,
                    template_type='reminder',
                    # CORREGIDO: Ahora son 3 variables
                    variables=[service_name, time_str, booking_url]
                )
                logger.info(f"✅ Recordatorio cliente enviado: {customer_phone}")
                sent_count += 1
            except Exception as e:
                logger.error(f"❌ Error enviando recordatorio a cliente: {e}")
            
            # ============================================
            # RECORDATORIO PARA EL PROVEEDOR
            # ============================================
            logger.info(f"📱 Enviando recordatorio a proveedor: {provider_phone}")
            
            try:
                whatsapp_service.send_message(
                    phone=provider_phone,
                    template_type='reminder',
                    # CORREGIDO: Ahora son 3 variables
                    variables=[service_name, time_str, booking_url]
                )
                logger.info(f"✅ Recordatorio proveedor enviado: {provider_phone}")
                sent_count += 1
            except Exception as e:
                logger.error(f"❌ Error enviando recordatorio a proveedor: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error procesando booking {booking.id}: {e}")
    
    logger.info(f"✅ Tarea completada. Total enviados: {sent_count}")
    return {'sent': sent_count, 'total_pending': pending_reminders.count()}


# ============================================
# TAREA: Enviar mensaje WhatsApp genérico
# ============================================

@shared_task
def send_whatsapp_message(phone, template_type, variables=None):
    """
    Envía un mensaje WhatsApp usando un template
    
    Args:
        phone: Número de teléfono (ej: 593998981436)
        template_type: Tipo de template (booking_created, booking_accepted, reminder, etc)
        variables: Lista de variables para el template [var1, var2, var3, ...]
    
    Returns:
        dict con status del envío
    """
    logger.info(f"📱 Enviando WhatsApp: {template_type} a {phone}")
    
    try:
        whatsapp_service = WhatsAppService()
        
        result = whatsapp_service.send_message(
            phone=phone,
            template_type=template_type,
            variables=variables or []
        )
        
        logger.info(f"✅ Mensaje enviado: {result}")
        return {'success': True, **result}
        
    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {'success': False, 'error': str(e)}


# ============================================
# TAREA: Reintentar mensajes fallidos
# ============================================

@shared_task
def retry_failed_messages():
    """
    Reintenta enviar mensajes WhatsApp que fallaron
    """
    logger.info("🔄 Iniciando reintento de mensajes fallidos...")
    
    # Obtener mensajes con error
    failed_logs = WhatsAppLog.objects.filter(
        status='error',
        retry_count__lt=3
    ).select_related('booking')[:10]
    
    logger.info(f"📋 Mensajes para reintentar: {failed_logs.count()}")
    
    retried_count = 0
    
    for log in failed_logs:
        try:
            if log.booking and log.template_variables:
                phone = log.recipient_phone
                template_type = log.template_name
                variables = log.template_variables
                
                # Reintentar
                send_whatsapp_message.delay(phone, template_type, variables)
                
                log.retry_count += 1
                log.save()
                
                logger.info(f"🔄 Mensaje reintentado: {log.id}")
                retried_count += 1
                
        except Exception as e:
            logger.error(f"❌ Error reintentando mensaje {log.id}: {e}")
    
    logger.info(f"✅ Reintento completado. Total reintentados: {retried_count}")
    return {'retried': retried_count}