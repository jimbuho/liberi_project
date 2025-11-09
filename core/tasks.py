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
        verification_url = f"{settings.BASE_URL}/verify-email/{token}/"
        
        html_message = render_to_string('emails/verification_email.html', {
            'user_name': user_name,
            'verification_url': verification_url,
        })
        
        send_mail(
            subject='Verifica tu email en Liberi',
            message='Por favor verifica tu email haciendo click en el enlace',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de verificación enviado a {user_email}")
        return f"Email enviado a {user_email}"
        
    except Exception as exc:
        logger.error(f"❌ Error enviando email a {user_email}: {exc}")
        # Reintentar en 60 segundos
        raise self.retry(exc=exc, countdown=60)