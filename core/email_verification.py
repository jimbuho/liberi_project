from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from .models import EmailVerificationToken
import os
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user, email):
    try:
        print(f"\n=== INICIANDO ENVÍO DE EMAIL DE VERIFICACIÓN ===")
        print(f"Usuario: {user.username}")
        print(f"Email: {email}")
        
        token = EmailVerificationToken.create_for_user(user, email)
        print(f"Token creado: {token.token[:20]}...")
        
        if os.environ.get('ENV') == 'development' or settings.DEBUG:
            base_url = 'http://localhost:8000'
        else:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        
        verification_url = f"{base_url}/verify-email/{token.token}/"
        print(f"URL de verificación: {verification_url}")
        
        try:
            html_message = render_to_string('auth/emails/verification_email.html', {
                'user_name': user.first_name or user.username,
                'verification_url': verification_url,
                'token_expiry': '24 horas',
            })
            print("Template HTML renderizado correctamente")
        except Exception as e:
            print(f"ERROR renderizando template HTML: {e}")
            html_message = None
        
        subject = "Verifica tu correo electrónico - Liberi"
        
        text_message = f"""
Hola {user.first_name or user.username},

Para completar tu registro, verifica tu correo electrónico usando este enlace:
{verification_url}

Este enlace expira en 24 horas.

Si no creaste una cuenta en Liberi, ignora este email.

Saludos,
El Equipo de Liberi
        """
        
        print(f"\nEmail backend: {settings.EMAIL_BACKEND}")
        print(f"From: {settings.DEFAULT_FROM_EMAIL}")
        print(f"To: {email}")
        
        result = send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"Email enviado. Resultado: {result}")
        print("=== EMAIL ENVIADO EXITOSAMENTE ===\n")
        
        logger.info(f"Email de verificación enviado a {email}")
        return True, "Email de verificación enviado correctamente"
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"\n❌ ERROR AL ENVIAR EMAIL DE VERIFICACIÓN: {error_msg}")
        print(f"Tipo de error: {type(e).__name__}")
        print("=== ERROR EN ENVÍO DE EMAIL ===\n")
        logger.error(f"Error enviando email de verificación a {email}: {error_msg}", exc_info=True)
        return False, error_msg


def send_welcome_email(user, is_provider=False):
    try:
        print(f"\n=== ENVIANDO EMAIL DE BIENVENIDA ===")
        print(f"Usuario: {user.username}")
        print(f"Es Proveedor: {is_provider}")
        
        try:
            html_message = render_to_string('auth/emails/welcome_email.html', {
                'user_name': user.first_name or user.username,
                'login_url': f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/login/",
                'is_provider': is_provider,
                'dashboard_url': f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/dashboard/",
                'year': timezone.now().year,
            })
            print("Template HTML renderizado correctamente")
        except Exception as e:
            print(f"ERROR renderizando template HTML: {e}")
            html_message = None
        
        subject = "¡Bienvenido a Liberi!"
        
        text_message = f"""
Hola {user.first_name or user.username},

¡Tu correo ha sido verificado exitosamente!

Ya puedes acceder a tu cuenta y comenzar a usar Liberi.

Inicia sesión en: {getattr(settings, 'BASE_URL', 'http://localhost:8000')}/login/

Saludos,
El Equipo de Liberi
        """
        
        print(f"To: {user.email}")
        
        result = send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"Email enviado. Resultado: {result}")
        print("=== EMAIL DE BIENVENIDA ENVIADO ===\n")
        
        logger.info(f"Email de bienvenida enviado a {user.email}")
        return True, "Email de bienvenida enviado correctamente"
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"\n❌ ERROR AL ENVIAR EMAIL DE BIENVENIDA: {error_msg}")
        print(f"Tipo de error: {type(e).__name__}")
        print("=== ERROR EN ENVÍO DE EMAIL ===\n")
        logger.error(f"Error enviando email de bienvenida a {user.email}: {error_msg}", exc_info=True)
        return False, error_msg