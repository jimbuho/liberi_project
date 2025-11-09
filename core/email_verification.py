# core/email_verification.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import EmailVerificationToken

def send_verification_email(user, email):
    """
    Envía un email de verificación al usuario
    """
    # Crear token
    token = EmailVerificationToken.create_for_user(user, email)
    
    # Construir URL de verificación
    verification_url = f"{settings.BASE_URL}/auth/verify-email/{token.token}/"
    
    # Renderizar template HTML
    html_message = render_to_string('auth/emails/verification_email.html', {
        'user_name': user.first_name or user.username,
        'verification_url': verification_url,
    })
    
    subject = "Verifica tu correo electrónico - Liberi"
    
    # Mensaje de texto plano (como fallback)
    text_message = f"""
    Hola {user.first_name or user.username},
    
    Para completar tu registro, verifica tu correo electrónico usando este enlace:
    {verification_url}
    
    Este enlace expira en 24 horas.
    
    Si no creaste una cuenta en Liberi, ignora este email.
    
    Saludos,
    El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Email de verificación enviado correctamente"
    except Exception as e:
        print(f"❌ Error al enviar email de verificación: {e}")
        return False, f"Error: {str(e)}"


def send_welcome_email(user, is_provider=False):
    """
    Envía un email de bienvenida después de verificar el correo
    """
    # Renderizar template HTML
    html_message = render_to_string('auth/emails/welcome_email.html', {
        'user_name': user.first_name or user.username,
        'login_url': f"{settings.BASE_URL}/login/",
        'is_provider': is_provider,
    })
    
    subject = "¡Bienvenido a Liberi!"
    
    # Mensaje de texto plano
    text_message = f"""
    Hola {user.first_name or user.username},
    
    ¡Tu correo ha sido verificado exitosamente!
    
    Ya puedes acceder a tu cuenta y comenzar a usar Liberi.
    
    Inicia sesión en: {settings.BASE_URL}/login/
    
    Saludos,
    El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        print(f"❌ Error al enviar email de bienvenida: {e}")