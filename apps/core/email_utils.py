"""
Utilidades centralizadas para el envío de correos electrónicos.
Previene el envío de emails en modo desarrollo.
"""

from django.core.mail import send_mail as django_send_mail, EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def should_send_emails():
    """
    Determina si se deben enviar emails basándose en el entorno.
    
    Returns:
        bool: True si se deben enviar emails, False en caso contrario
    """
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    return environment == 'production'


def run_task(task, *args, **kwargs):
    """
    Ejecuta una tarea de Celery de forma inteligente según el entorno.
    
    En desarrollo: Ejecuta la tarea síncronamente (sin Redis/Celery)
    En producción: Encola la tarea con .delay()
    
    Args:
        task: La función de tarea de Celery
        *args: Argumentos posicionales para la tarea
        **kwargs: Argumentos nombrados para la tarea
        
    Returns:
        El resultado de la tarea (en desarrollo) o el AsyncResult (en producción)
        
    Example:
        from apps.core.email_utils import run_task
        from apps.core.tasks import send_verification_email_task
        
        run_task(send_verification_email_task, user_id=1, user_email='test@example.com')
    """
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    
    if environment == 'development':
        # En desarrollo: ejecutar síncronamente
        logger.info(f"🔧 [DEVELOPMENT] Ejecutando tarea '{task.__name__}' síncronamente")
        return task(*args, **kwargs)
    else:
        # En producción: usar Celery
        logger.info(f"📤 [PRODUCTION] Encolando tarea '{task.__name__}' en Celery")
        return task.delay(*args, **kwargs)


def send_mail(subject, message, from_email, recipient_list, fail_silently=False, **kwargs):
    """
    Wrapper de django.core.mail.send_mail que previene envío en desarrollo.
    
    Args:
        subject: Asunto del email
        message: Mensaje del email
        from_email: Email del remitente
        recipient_list: Lista de destinatarios
        fail_silently: Si debe fallar silenciosamente
        **kwargs: Argumentos adicionales para send_mail
        
    Returns:
        int: Número de emails enviados (0 si está en desarrollo)
    """
    if not should_send_emails():
        logger.info(
            f"📧 [DEVELOPMENT MODE] Email NO enviado:\n"
            f"   Para: {recipient_list}\n"
            f"   Asunto: {subject}\n"
            f"   Mensaje: {message[:100]}..."
        )
        return 0
    
    logger.info(f"📧 [PRODUCTION] Enviando email a {recipient_list}: {subject}")
    return django_send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=fail_silently,
        **kwargs
    )


def send_html_email(subject, text_content, html_content, from_email, recipient_list, fail_silently=False):
    """
    Envía un email con contenido HTML y texto plano.
    Previene envío en modo desarrollo.
    
    Args:
        subject: Asunto del email
        text_content: Contenido en texto plano
        html_content: Contenido en HTML
        from_email: Email del remitente
        recipient_list: Lista de destinatarios
        fail_silently: Si debe fallar silenciosamente
        
    Returns:
        int: Número de emails enviados (0 si está en desarrollo)
    """
    if not should_send_emails():
        logger.info(
            f"📧 [DEVELOPMENT MODE] Email HTML NO enviado:\n"
            f"   Para: {recipient_list}\n"
            f"   Asunto: {subject}\n"
            f"   Texto: {text_content[:100]}..."
        )
        return 0
    
    logger.info(f"📧 [PRODUCTION] Enviando email HTML a {recipient_list}: {subject}")
    
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=recipient_list
    )
    email_message.attach_alternative(html_content, "text/html")
    
    try:
        return email_message.send(fail_silently=fail_silently)
    except Exception as e:
        if not fail_silently:
            raise
        logger.error(f"Error enviando email: {e}")
        return 0
