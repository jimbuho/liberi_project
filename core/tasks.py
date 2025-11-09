# core/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, user_email, token, user_name):
    """Envía email de verificación de forma asincrónica"""
    try:
        # 🔧 FIX - SIN /auth/
        verification_url = f"{settings.BASE_URL}/verify-email/{token}/"
        
        print(f"📧 [CELERY] Enviando email a {user_email}")
        print(f"📧 [CELERY] URL: {verification_url}")
        
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
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de verificación enviado a {user_email}")
        print(f"✅ [CELERY] Email enviado exitosamente")
        return f"Email enviado a {user_email}"
        
    except Exception as exc:
        logger.error(f"❌ Error enviando email a {user_email}: {exc}")
        print(f"❌ [CELERY] Error: {exc}")
        # Reintentar en 60 segundos (máximo 3 intentos)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_welcome_email_task(self, user_email, user_name, is_provider=False):
    """Envía email de bienvenida después de verificar"""
    try:
        html_message = render_to_string('auth/emails/welcome_email.html', {
            'user_name': user_name,
            'login_url': f"{settings.BASE_URL}/login/",
            'is_provider': is_provider,
        })
        
        text_message = f"""
Hola {user_name},

¡Tu correo ha sido verificado exitosamente!

Ya puedes acceder a tu cuenta y comenzar a usar Liberi.

Inicia sesión en: {settings.BASE_URL}/login/

Saludos,
El Equipo de Liberi
        """
        
        send_mail(
            subject='¡Bienvenido a Liberi!',
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de bienvenida enviado a {user_email}")
        
    except Exception as exc:
        logger.error(f"❌ Error enviando email de bienvenida a {user_email}: {exc}")
        raise self.retry(exc=exc, countdown=60)