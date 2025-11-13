from celery import shared_task
from datetime import datetime, timedelta
from django.utils import timezone
import logging

from .services import WhatsAppService


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_message(self, recipient, template_name, variables):
    """
    Tarea asíncrona para enviar mensajes de WhatsApp
    
    Args:
        recipient: Número de teléfono del destinatario
        template_name: Nombre de la plantilla de WhatsApp
        variables: Lista de variables para la plantilla
    """
    try:
        logger.info(f"📱 Enviando WhatsApp: {template_name} a {recipient}")
        log = WhatsAppService.send_message(recipient, template_name, variables)
        
        if log.status == 'failed':
            logger.warning(f"⚠️ Fallo en envío de WhatsApp: {log.error_message}")
            # Reintentar si hay error
            raise Exception(f"Fallo en envío: {log.error_message}")
        
        logger.info(f"✅ WhatsApp enviado exitosamente (Log ID: {log.id})")
        return {
            'success': True,
            'log_id': log.id,
            'message_id': log.message_id,
            'status': log.status
        }
        
    except Exception as exc:
        logger.error(f"❌ Error en send_whatsapp_message: {exc}")
        # Reintentar hasta 3 veces
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Reintentando envío ({self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=exc)
        else:
            logger.error(f"❌ Máximo de reintentos alcanzado para {recipient}")
            return {
                'success': False,
                'error': str(exc)
            }


@shared_task
def send_service_reminders():
    """
    Tarea programada que se ejecuta cada 15 minutos para enviar recordatorios
    de servicios que están próximos a ocurrir (1 hora antes)
    """
    from core.models import Booking
    
    logger.info("🔔 Ejecutando tarea de recordatorios de servicios...")
    
    now = timezone.now()
    target_time = now + timedelta(hours=1)
    
    # Ventana de búsqueda: entre 1 hora y 1 hora 15 minutos en el futuro
    time_window_start = target_time
    time_window_end = target_time + timedelta(minutes=15)
    
    # Buscar reservas pagadas en la ventana de tiempo
    upcoming_bookings = Booking.objects.filter(
        scheduled_time__gte=time_window_start,
        scheduled_time__lt=time_window_end,
        payment_status='paid',
        status__in=['pending', 'accepted']
    ).select_related('customer', 'provider')
    
    count = upcoming_bookings.count()
    logger.info(f"📋 Encontradas {count} reserva(s) próximas en la ventana de tiempo")
    
    reminders_sent = 0
    
    for booking in upcoming_bookings:
        try:
            # Obtener información del servicio
            service_name = booking.get_services_display()
            time_str = booking.scheduled_time.strftime('%H:%M')
            
            # Obtener números de teléfono
            customer_phone = getattr(booking.customer.profile, 'phone', None)
            provider_phone = getattr(booking.provider.profile, 'phone', None)
            
            # Enviar recordatorio al cliente
            if customer_phone:
                send_whatsapp_message.delay(
                    recipient=customer_phone,
                    template_name='reminder',
                    variables=[service_name, time_str]
                )
                logger.info(f"📨 Recordatorio enviado al cliente {booking.customer.username}")
                reminders_sent += 1
            else:
                logger.warning(f"⚠️ Cliente {booking.customer.username} no tiene teléfono registrado")
            
            # Enviar recordatorio al proveedor
            if provider_phone:
                send_whatsapp_message.delay(
                    recipient=provider_phone,
                    template_name='reminder',
                    variables=[service_name, time_str]
                )
                logger.info(f"📨 Recordatorio enviado al proveedor {booking.provider.username}")
                reminders_sent += 1
            else:
                logger.warning(f"⚠️ Proveedor {booking.provider.username} no tiene teléfono registrado")
                
        except Exception as e:
            logger.error(f"❌ Error enviando recordatorio para booking {booking.id}: {e}")
    
    logger.info(f"✅ Tarea de recordatorios completada. {reminders_sent} mensaje(s) enviado(s)")
    
    return {
        'bookings_found': count,
        'reminders_sent': reminders_sent
    }