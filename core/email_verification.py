# core/email_verification.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import EmailVerificationToken
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user, email):
    """
    Envía un email de verificación - ASINCRÓNICO con Celery
    """
    try:
        # Crear token ANTES de encolar la tarea
        token_obj = EmailVerificationToken.create_for_user(user, email)
        token = token_obj.token
        
        print(f"\n=== INICIANDO ENVÍO DE EMAIL DE VERIFICACIÓN ===")
        print(f"Usuario: {user.username}")
        print(f"Email: {email}")
        print(f"Token creado: {token}")
        print(f"Token valid: {token_obj.is_valid()}")
        
        # Intenta enviar con Celery si está disponible
        try:
            from core.tasks import send_verification_email_task
            send_verification_email_task.delay(
                user_email=email,
                token=token,
                user_name=user.first_name or user.username
            )
            print("✅ Tarea enviada a Celery")
        except Exception as celery_error:
            # Si Celery falla, intenta envío sincrónico como fallback
            logger.warning(f"Celery no disponible, intentando envío sincrónico: {celery_error}")
            _send_email_sync(email, token, user.first_name or user.username)
        
        return True, "Email de verificación enviado exitosamente"
        
    except Exception as e:
        logger.error(f"❌ Error al enviar email: {e}")
        print(f"❌ ERROR: {e}")
        return False, f"Error al enviar email: {str(e)}"


def _send_email_sync(email, token, user_name):
    """Envío sincrónico como fallback"""
    verification_url = f"{settings.BASE_URL}/verify-email/{token}/"
    
    print(f"📧 URL de verificación: {verification_url}")
    
    html_message = render_to_string('auth/emails/verification_email.html', {
        'user_name': user_name,
        'verification_url': verification_url,
    })
    
    text_message = f"""
Hola {user_name},

Para completar tu registro, verifica tu correo electrónico usando este enlace:
{verification_url}

Este enlace expira en 24 horas.

Si no creaste una cuenta en Liberi, ignora este email.

Saludos,
El Equipo de Liberi
    """
    
    send_mail(
        subject='Verifica tu correo electrónico - Liberi',
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,
    )
    print("✅ Email enviado sincronamente")


def send_welcome_email(user, is_provider=False):
    """Envía email de bienvenida - ASINCRÓNICO"""
    try:
        from core.tasks import send_welcome_email_task
        send_welcome_email_task.delay(
            user_email=user.email,
            user_name=user.first_name or user.username,
            is_provider=is_provider
        )
    except Exception as e:
        logger.error(f"❌ Error al enviar email de bienvenida: {e}")