from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Avg, Count, Sum
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
import json
import logging
from datetime import datetime, timedelta

from apps.core.models import (
    Profile, ProviderProfile, Service, Category, 
    AuditLog, EmailVerificationToken, PasswordResetToken
)

from apps.core.image_upload import upload_profile_photo, replace_image, upload_image

from apps.core.email_verification import send_verification_email, send_welcome_email, resend_verification_email
from apps.core.tasks import send_password_reset_email_task, send_provider_approval_notification_task
from apps.legal.models import LegalDocument, LegalAcceptance
from apps.legal.views import get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

def get_active_categories():
    return Category.objects.all().order_by('name')

def login_view(request):
    """
    Login de usuario - Soporta EMAIL o USERNAME
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username_or_email or not password:
            messages.error(request, 'Por favor ingresa usuario/email y contraseña')
            return render(request, 'auth/login.html')
        
        # Paso 1: Intentar encontrar el usuario por email O username
        user = None
        
        # Buscar por email
        try:
            user = User.objects.get(email=username_or_email)
            username = user.username  # Usar el username para authenticate
        except User.DoesNotExist:
            pass
        
        # Si no encontró por email, buscar por username
        if user is None:
            username = username_or_email
            try:
                user = User.objects.get(username=username_or_email)
            except User.DoesNotExist:
                user = None
        
        # Paso 2: Autenticar con Django
        if user is not None:
            authenticated_user = authenticate(request, username=user.username, password=password)
        else:
            authenticated_user = None
        
        # Paso 3: Verificar contraseña y estado de cuenta
        if authenticated_user is not None:
            # Verificar que el email esté verificado
            if not authenticated_user.profile.verified:
                messages.error(
                    request, 
                    'Tu cuenta no ha sido verificada. Revisa tu email para activarla.'
                )
                return render(request, 'auth/login.html')
            
            # Login exitoso
            login(request, authenticated_user)
            
            # Log de auditoría
            AuditLog.objects.create(
                user=authenticated_user,
                action='Inicio de sesión',
                metadata={'ip': get_client_ip(request)}
            )
            
            messages.success(
                request, 
                f'¡Bienvenido, {authenticated_user.first_name or authenticated_user.username}!'
            )
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            messages.error(request, 'Usuario/Email o contraseña incorrectos.')
            return render(request, 'auth/login.html')
    
    return render(request, 'auth/login.html')


def register_view(request):
    """Registro de cliente"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        terms_accepted = request.POST.get('terms_accepted')

        # Validaciones
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register.html')
        
        # NUEVA VALIDACIÓN
        if not terms_accepted:
            messages.error(request, 'Debes aceptar los Términos de Uso y Política de Privacidad')
            return render(request, 'auth/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'auth/register.html')
        
        try:
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Crear perfil
            profile = Profile(user=user, phone=phone, role='customer')
            profile.full_clean()  # Ejecuta las validaciones
            profile.save()
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')
            return render(request, 'auth/register.html')
        

        try:
            for doc_type in ['terms_user', 'privacy_user']:
                try:
                    document = LegalDocument.objects.get(
                        document_type=doc_type,
                        is_active=True,
                        status='published'
                    )
                    
                    LegalAcceptance.objects.get_or_create(
                        user=user,
                        document=document,
                        defaults={
                            'ip_address': get_client_ip(request),
                            'user_agent': get_user_agent(request),
                        }
                    )
                except LegalDocument.DoesNotExist:
                    pass
        except Exception as e:
            logger.warning(f"Error registrando aceptación legal: {e}")
        
        # 🔥 ENVIAR EMAIL EN SEGUNDO PLANO (NO BLOQUEA)
        success, message = send_verification_email(user, email)
        
        if not success:
            print(f"Email de verificación no se encendió para {email}: {message}")
            # No falles el registro, solo advierte
        
        # Crear entry de verificación para redirigir
        messages.success(
            request,
            '¡Registro exitoso! Te hemos enviado un email de verificación. '
            'Por favor, revisa tu bandeja de entrada.'
        )
        
        # Redirigir a página de espera de verificación
        return redirect('email_verification_pending_view')
    
    return render(request, 'auth/register.html')


def register_provider_view(request):
    """Registro de proveedor CON VERIFICACIÓN DE EMAIL"""
    if request.user.is_authenticated:
        messages.info(request, 'Ya tienes una sesión activa')
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        business_name = request.POST.get('business_name')
        profile_photo = request.FILES.get('profile_photo')
        terms_accepted = request.POST.get('terms_accepted')
        
        # Helper para preservar datos del formulario (excluyendo passwords)
        form_data = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'business_name': business_name,
            'description': description,
            'category': int(category_id) if category_id else None,
            'terms_accepted': terms_accepted
        }

        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })

        # NUEVA VALIDACIÓN
        if terms_accepted is None or not terms_accepted:
            messages.error(request, 'Debes aceptar los Términos de Uso y Política de Privacidad')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })
        
        if not profile_photo:
            messages.error(request, 'La foto de perfil es obligatoria')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=False
            )

            photo_url = upload_profile_photo(
                file=profile_photo,
                user_id=user.id
            )
            
            # Crear perfil
            profile = Profile(user=user, phone=phone, role='provider')
            profile.full_clean()  # Ejecuta las validaciones
            profile.save()
            
            ProviderProfile.objects.create(
                user=user,
                category_id=category_id,
                description=description,
                business_name=business_name,
                profile_photo=photo_url,
                status='created',
                registration_step=1
            )

            try:
                for doc_type in ['terms_user', 'privacy_user']:
                    try:
                        document = LegalDocument.objects.get(
                            document_type=doc_type,
                            is_active=True,
                            status='published'
                        )
                        
                        LegalAcceptance.objects.get_or_create(
                            user=user,
                            document=document,
                            defaults={
                                'ip_address': get_client_ip(request),
                                'user_agent': get_user_agent(request),
                            }
                        )
                    except LegalDocument.DoesNotExist:
                        pass
            except Exception as e:
                logger.warning(f"Error registrando aceptación legal: {e}")
            
            success, message = send_verification_email(user, email)
            
            if success:
                messages.success(
                    request,
                    '¡Perfil creado! Te hemos enviado un email de verificación. '
                    'Completa la verificación para acceder a tu cuenta y continuar con la verificación de identidad.'
                )
                
                AuditLog.objects.create(
                    user=user,
                    action='Registro de proveedor iniciado - Esperando verificación de email',
                    metadata={
                        'email': email,
                        'business_name': business_name
                    }
                )
                
                return redirect('login')
            else:
                user.delete()
                messages.error(request, f'Error al enviar email: {message}')
                return render(request, 'auth/register_provider.html', {
                    'categories': get_active_categories(),
                    'form_data': form_data
                })

        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })
        except Exception as e:
            try:
                user = User.objects.get(username=username)
                user.delete()
            except:
                pass
            print(f'Error al crear perfil: {str(e)}')
            messages.error(request, f'Error al crear perfil: {str(e)}')
            return render(request, 'auth/register_provider.html', {
                'categories': get_active_categories(),
                'form_data': form_data
            })

    context = {
        'categories': get_active_categories(),
    }
    return render(request, 'auth/register_provider.html', context)

@login_required
def provider_register_step2(request):
    """
    Segundo paso del registro de proveedor: Verificación de identidad
    """
    # Verificar que sea proveedor
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden acceder a esta página')
        return redirect('home')
    
    # Verificar que tenga perfil de proveedor
    if not hasattr(request.user, 'provider_profile'):
        messages.error(request, 'No tienes un perfil de proveedor')
        return redirect('home')
    
    provider_profile = request.user.provider_profile
    
    # Verificar que esté en el paso correcto
    if provider_profile.registration_step >= 2:
        messages.info(request, 'Ya completaste la verificación de identidad')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Obtener archivos
        id_card_front = request.FILES.get('id_card_front')
        id_card_back = request.FILES.get('id_card_back')
        selfie_with_id = request.FILES.get('selfie_with_id')
        
        # Validar que se subieron las 3 imágenes
        if not all([id_card_front, id_card_back, selfie_with_id]):
            messages.error(request, 'Debes subir las 3 imágenes requeridas')
            return render(request, 'auth/register_step2.html', {
                'provider_profile': provider_profile
            })
        
        # Validar tamaño de archivos
        for file in [id_card_front, id_card_back, selfie_with_id]:
            if file.size > 7 * 1024 * 1024:  # 5MB
                messages.error(request, f'La imagen {file.name} supera el tamaño máximo de 5MB')
                return render(request, 'auth/register_step2.html', {
                    'provider_profile': provider_profile
                })
        
        try:
            # Subir imágenes a Supabase/Storage
            
            front_url = upload_image(
                file=id_card_front,
                folder='documents/id_cards',
                user_id=request.user.id,
                prefix='front'
            )
            
            back_url = upload_image(
                file=id_card_back,
                folder='documents/id_cards',
                user_id=request.user.id,
                prefix='back'
            )
            
            selfie_url = upload_image(
                file=selfie_with_id,
                folder='documents/selfies',
                user_id=request.user.id,
                prefix='selfie'
            )
            
            # CORRECCIÓN: Actualizar perfil pero MANTENER status='created'
            provider_profile.id_card_front = front_url
            provider_profile.id_card_back = back_url
            provider_profile.selfie_with_id = selfie_url
            provider_profile.registration_step = 2
            provider_profile.status = 'created'  # Mantener en 'created', NO cambiar a 'pending'
            provider_profile.documents_verified = False  # Documentos aún no verificados
            provider_profile.save()
            
            # TRIGGER VALIDATION: Si ya tiene servicio, validar ahora
            from apps.core.verification import trigger_validation_if_eligible
            
            triggered = trigger_validation_if_eligible(provider_profile)
            
            if triggered:
                messages.success(request, '¡Documentos subidos! Tu perfil ha entrado en proceso de verificación.')
            else:
                # Si no se disparó (probablemente falta servicio)
                if provider_profile.status == 'created':
                    messages.success(
                        request,
                        '¡Documentos subidos exitosamente! '
                        'Ahora crea tu primer servicio para solicitar la aprobación de tu perfil.'
                    )
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error al subir documentos: {str(e)}')
            return render(request, 'auth/register_step2.html', {
                'provider_profile': provider_profile
            })
    
    context = {
        'provider_profile': provider_profile
    }
    return render(request, 'auth/register_step2.html', context)

def verify_email_view(request, token):
    """Verifica el email del usuario usando el token"""
    logger.info(f"Verificando email con token: {token}")
    
    try:
        verification_token = EmailVerificationToken.objects.get(token=token)
        print(f"Token encontrado en BD: {verification_token.token}")
        print(f"¿Es válido?: {verification_token.is_valid()}")
    except EmailVerificationToken.DoesNotExist:
        print(f"❌ Token NO encontrado en BD")
        messages.error(request, 'Token de verificación inválido o expirado')
        return redirect('home')
    
    # Validar que el token sea válido
    if not verification_token.is_valid():
        print(f"❌ Token expirado o ya verificado")
        messages.error(request, 'El token de verificación ha expirado')
        return redirect('home')
    
    # Verificar el token
    verification_token.verify()
    print(f"✅ Token verificado")
    
    # Activar usuario
    user = verification_token.user
    user.is_active = True
    user.save()
    
    # 🔥 MARCAR PERFIL COMO VERIFICADO
    user.profile.verified = True
    user.profile.save()
    print(f"✅ Perfil de {user.username} marcado como VERIFICADO")
    
    # Determinar si es proveedor
    is_provider = user.profile.role == 'provider'
    
    # Enviar email de bienvenida
    send_welcome_email(user, is_provider=is_provider)
    
    # Log
    AuditLog.objects.create(
        user=user,
        action='Email verificado',
        metadata={'email': user.email}
    )
    
    messages.success(
        request,
        '✓ Email verificado exitosamente. Tu cuenta está activa. Ya puedes iniciar sesión.'
    )
    
    return redirect('login')

def email_verification_pending(request):
    """Página que se muestra mientras se espera verificación"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Si el email ya está verificado, redirigir al dashboard
    if request.user.profile.verified:
        messages.success(request, '✅ Tu email ya ha sido verificado!')
        return redirect('dashboard')
    
    context = {
        'user_email': request.user.email,
    }
    return render(request, 'auth/email_verification_pending.html', context)

@login_required
def resend_verification_view(request):
    """Reenvía el email de verificación"""
    if request.method == 'POST':
        # Verificar que no esté ya verificado
        if request.user.profile.verified:
            messages.info(request, 'Tu email ya está verificado')
            return redirect('dashboard')
        
        # Reenviar email
        success, message = resend_verification_email(request.user)
        
        if success:
            messages.success(
                request,
                '✓ Email de verificación reenviado. Revisa tu bandeja de entrada.'
            )
        else:
            messages.error(request, f'Error al reenviar: {message}')
        
        return redirect('email_verification_pending_view')
    
    return redirect('email_verification_pending_view')

@login_required
def logout_view(request):
    """Logout"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('home')

def forgot_password_view(request):
    """
    Vista para que el usuario solicite reset de contraseña
    GET: Muestra el formulario
    POST: Envía email con enlace de reset
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Por favor ingresa tu email')
            return render(request, 'auth/forgot_password.html')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.success(
                request,
                '✓ Si existe una cuenta con ese email, recibirás un enlace para resetear tu contraseña.'
            )
            return redirect('forgot_password')
        
        try:
            reset_token = PasswordResetToken.create_for_user(user)

            send_password_reset_email_task.delay(
                user_id=user.id,
                token=reset_token.token
            )
            
            AuditLog.objects.create(
                user=user,
                action='Solicitud de reset de contraseña',
                metadata={'email': email}
            )
            
            messages.success(
                request,
                '✓ Si existe una cuenta con ese email, recibirás un enlace para resetear tu contraseña.'
            )
            return redirect('login')
            
        except Exception as e:
            logger.error(f"Error en forgot_password: {e}")
            messages.error(request, 'Error al procesar tu solicitud. Intenta nuevamente.')
            return render(request, 'auth/forgot_password.html')
    
    return render(request, 'auth/forgot_password.html')


def reset_password_view(request, token):
    """
    Vista para resetear la contraseña con token
    GET: Muestra el formulario de nueva contraseña
    POST: Actualiza la contraseña
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Enlace de reset inválido')
        return redirect('forgot_password')
    
    if not reset_token.is_valid():
        messages.error(request, 'El enlace de reset ha expirado. Solicita uno nuevo.')
        reset_token.delete_if_expired()
        return redirect('forgot_password')
    
    user = reset_token.user
    
    if request.method == 'POST':
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        if not password or not password_confirm:
            messages.error(request, 'Por favor completa todos los campos')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        try:
            validate_password(password, user=user)
        except Exception as e:
            messages.error(request, f'Contraseña débil: {str(e)}')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        try:
            user.set_password(password)
            user.save()
            
            reset_token.mark_as_used()
            
            AuditLog.objects.create(
                user=user,
                action='Contraseña reseteada',
                metadata={}
            )
            
            messages.success(
                request,
                '✓ Tu contraseña ha sido actualizada. Ahora puedes iniciar sesión con tu nueva contraseña.'
            )
            return redirect('login')
            
        except Exception as e:
            logger.error(f"Error reseteando contraseña: {e}")
            messages.error(request, 'Error al actualizar tu contraseña. Intenta nuevamente.')
            return render(request, 'auth/reset_password.html', {'token': token})
    
    return render(request, 'auth/reset_password.html', {
        'token': token,
        'user_email': user.email
    })


@login_required
def change_password_view(request):
    """
    Vista para que el usuario cambie su contraseña estando autenticado
    (Desde el perfil/dashboard)
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        new_password_confirm = request.POST.get('new_password_confirm', '')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Tu contraseña actual es incorrecta')
            return render(request, 'dashboard/change_password.html')
        
        if new_password != new_password_confirm:
            messages.error(request, 'Las nuevas contraseñas no coinciden')
            return render(request, 'dashboard/change_password.html')
        
        if len(new_password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
            return render(request, 'dashboard/change_password.html')
        
        if current_password == new_password:
            messages.error(request, 'Tu nueva contraseña debe ser diferente a la actual')
            return render(request, 'dashboard/change_password.html')
        
        try:
            validate_password(new_password, user=request.user)
        except Exception as e:
            messages.error(request, f'Contraseña débil: {str(e)}')
            return render(request, 'dashboard/change_password.html')
        
        try:
            request.user.set_password(new_password)
            request.user.save()
            
            AuditLog.objects.create(
                user=request.user,
                action='Contraseña cambiada',
                metadata={'from_profile': True}
            )
            
            messages.success(
                request,
                '✓ Tu contraseña ha sido actualizada exitosamente.'
            )
            
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            return redirect('dashboard')
            
        except Exception as e:
            logger.error(f"Error cambiando contraseña: {e}")
            messages.error(request, 'Error al cambiar tu contraseña. Intenta nuevamente.')
            return render(request, 'dashboard/change_password.html')
    
    return render(request, 'dashboard/change_password.html')


@login_required
def complete_provider_profile_google(request):
    """
    Vista para completar el perfil de proveedor después de registrarse con Google
    """
    # Verificar que sea proveedor
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'provider':
        messages.error(request, 'Esta página es solo para proveedores')
        return redirect('dashboard')
    
    # Verificar que no tenga ya un perfil de proveedor completo
    if hasattr(request.user, 'provider_profile'):
        messages.info(request, 'Ya tienes un perfil de proveedor completado')
        return redirect('dashboard')
    
    if request.method == 'POST':
        business_name = request.POST.get('business_name')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        profile_photo = request.FILES.get('profile_photo')
        phone = request.POST.get('phone')
        terms_accepted = request.POST.get('terms_accepted')
        
        # Validaciones
        if not all([business_name, category_id, description, profile_photo, phone]):
            messages.error(request, 'Todos los campos son obligatorios')
            return render(request, 'auth/complete_provider_profile_google.html', {
                'categories': get_active_categories(),
            })
        
        if not terms_accepted:
            messages.error(request, 'Debes aceptar los Términos de Uso y Política de Privacidad')
            return render(request, 'auth/complete_provider_profile_google.html', {
                'categories': get_active_categories(),
            })
        
        try:
            # Actualizar teléfono en el perfil
            request.user.profile.phone = phone
            request.user.profile.save()
            
            # Subir foto
            photo_url = upload_profile_photo(
                file=profile_photo,
                user_id=request.user.id
            )
            
            # Crear perfil de proveedor
            ProviderProfile.objects.create(
                user=request.user,
                category_id=category_id,
                description=description,
                business_name=business_name,
                profile_photo=photo_url,
                status='created',
                registration_step=1
            )
            
            # Registrar aceptación de términos legales
            try:
                for doc_type in ['terms_provider', 'privacy_provider']:
                    try:
                        document = LegalDocument.objects.get(
                            document_type=doc_type,
                            is_active=True,
                            status='published'
                        )
                        
                        LegalAcceptance.objects.get_or_create(
                            user=request.user,
                            document=document,
                            defaults={
                                'ip_address': get_client_ip(request),
                                'user_agent': get_user_agent(request),
                            }
                        )
                    except LegalDocument.DoesNotExist:
                        pass
            except Exception as e:
                logger.warning(f"Error registrando aceptación legal: {e}")
            
            # Log
            AuditLog.objects.create(
                user=request.user,
                action='Perfil de proveedor completado (Google)',
                metadata={
                    'business_name': business_name,
                    'via': 'google_oauth'
                }
            )
            
            messages.success(
                request,
                '✅ Perfil de proveedor creado. Ahora sube tus documentos de verificación.'
            )
            return redirect('provider_register_step2')
            
        except Exception as e:
            messages.error(request, f'Error al crear perfil: {str(e)}')
            return render(request, 'auth/complete_provider_profile_google.html', {
                'categories': get_active_categories(),
            })
    
    context = {
        'categories': get_active_categories(),
        'user': request.user,
    }
    return render(request, 'auth/complete_provider_profile_google.html', context)


def google_provider_signup(request):
    """
    Vista intermedia que marca en sesión que es un registro de proveedor
    antes de redirigir a Google OAuth
    """
    # Marcar que es registro de proveedor
    request.session['is_provider_signup'] = True
    request.session.modified = True
    
    # Log para debug
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Iniciando registro de proveedor con Google")
    logger.info(f"Sesión marcada: is_provider_signup = {request.session.get('is_provider_signup')}")
    
    # Obtener la URL del provider
    google_login_url = reverse('google_login')
    
    # Redirigir a Google
    return HttpResponseRedirect(google_login_url)
