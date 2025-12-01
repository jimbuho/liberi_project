# core/email_verification.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from apps.core.models import EmailVerificationToken, AuditLog
from apps.core.email_utils import run_task
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user, email):
    """
    Envía email de verificación de forma asíncrona usando Celery
    Returns: (success: bool, message: str)
    """
    try:
        # Crear token
        verification_token = EmailVerificationToken.create_for_user(user, email)
        
        # Construir URL de verificación
        verification_url = f"{settings.BASE_URL}/verify-email/{verification_token.token}/"
        
        # Log
        logger.info(f"Token de verificación creado para {user.username}: {verification_token.token}")
        logger.info(f"URL de verificación: {verification_url}")
        
        # Ejecutar tarea (síncrona en dev, asíncrona en prod)
        from core.tasks import send_verification_email_task
        run_task(
            send_verification_email_task,
            user_id=user.id,
            user_email=email,
            verification_url=verification_url,
            user_name=user.get_full_name() or user.username
        )
        
        # Log de auditoría
        AuditLog.objects.create(
            user=user,
            action='Email de verificación enviado',
            metadata={
                'email': email,
                'token_created': True
            }
        )
        
        return True, "Email de verificación enviado"
        
    except Exception as e:
        logger.error(f"Error enviando email de verificación a {email}: {str(e)}", exc_info=True)
        return False, str(e)


def send_welcome_email(user, is_provider=False):
    """
    Envía email de bienvenida después de verificar email
    """
    try:
        from core.tasks import send_welcome_email_task
        run_task(
            send_welcome_email_task,
            user_id=user.id,
            user_email=user.email,
            user_name=user.get_full_name() or user.username,
            is_provider=is_provider
        )
        
        logger.info(f"Email de bienvenida encolado para {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida: {e}")
        return False


def resend_verification_email(user):
    """
    Reenvía el email de verificación
    Returns: (success: bool, message: str)
    """
    try:
        # Verificar que no esté ya verificado
        if user.profile.verified:
            return False, "El email ya está verificado"
        
        # Eliminar tokens antiguos
        EmailVerificationToken.objects.filter(user=user).delete()
        
        # Enviar nuevo email
        return send_verification_email(user, user.email)
        
    except Exception as e:
        logger.error(f"Error reenviando email de verificación: {e}")
        return False, str(e)