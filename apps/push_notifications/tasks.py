from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import logging

from .services import OneSignalService

logger = logging.getLogger(__name__)


@shared_task
def send_push_notification(user_id=None, player_ids=None, title="", 
                           message="", notification_type="general", 
                           data=None, url=None):
    """
    Tarea asíncrona para enviar notificación push
    
    Args:
        user_id: ID del usuario
        player_ids: Lista de player_ids (alternativa a user_id)
        title: Título
        message: Mensaje
        notification_type: Tipo de notificación
        data: Datos adicionales
        url: URL a abrir
    """
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Usuario {user_id} no encontrado")
                return {'success': False, 'error': 'Usuario no encontrado'}
        
        log = OneSignalService.send_notification(
            user=user,
            player_ids=player_ids,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data,
            url=url
        )
        
        return {
            'success': log.status == 'sent',
            'log_id': log.id,
            'onesignal_id': log.onesignal_id
        }
        
    except Exception as e:
        logger.error(f"Error en send_push_notification: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task
def send_push_reminders():
    """
    Envía recordatorios push 1 hora antes del servicio
    Similar a send_service_reminders de WhatsApp
    """
    from apps.core.models import Booking
    
    logger.info("🔔 Iniciando envío de recordatorios Push...")
    
    now = timezone.now()
    time_window_start = now + timedelta(minutes=45)
    time_window_end = now + timedelta(minutes=75)
    
    # Reservas que necesitan recordatorio
    pending_reminders = Booking.objects.filter(
        scheduled_time__gte=time_window_start,
        scheduled_time__lte=time_window_end,
        status='accepted',
        payment_status='paid'
    ).select_related('customer', 'provider')
    
    logger.info(f"📋 Reservas para recordatorio: {pending_reminders.count()}")
    
    sent_count = 0
    
    for booking in pending_reminders:
        try:
            # Servicio
            if booking.service_list and len(booking.service_list) > 0:
                service_name = booking.service_list[0].get('name', 'Servicio')
            else:
                service_name = 'Servicio'
            
            time_str = booking.scheduled_time.strftime("%H:%M")
            booking_url = f"{settings.SITE_URL}/bookings/{booking.slug if booking.slug else booking.id}/"
            
            # Recordatorio al cliente
            if booking.customer:
                send_push_notification.delay(
                    user_id=booking.customer.id,
                    title="🔔 Recordatorio de Servicio",
                    message=f"Tu servicio de {service_name} es a las {time_str}",
                    notification_type="reminder",
                    url=booking_url,
                    data={
                        'booking_id': str(booking.id),
                        'service': service_name,
                        'time': time_str
                    }
                )
                sent_count += 1
            
            # Recordatorio al proveedor
            if booking.provider:
                send_push_notification.delay(
                    user_id=booking.provider.id,
                    title="🔔 Recordatorio de Servicio",
                    message=f"Tienes un servicio de {service_name} a las {time_str}",
                    notification_type="reminder",
                    url=booking_url,
                    data={
                        'booking_id': str(booking.id),
                        'service': service_name,
                        'time': time_str
                    }
                )
                sent_count += 1
                
        except Exception as e:
            logger.error(f"Error enviando recordatorio push para booking {booking.id}: {e}")
    
    logger.info(f"✅ Recordatorios Push encolados: {sent_count}")
    return {'sent': sent_count, 'total_pending': pending_reminders.count()}
