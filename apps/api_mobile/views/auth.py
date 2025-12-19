from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.conf import settings
import logging

from ..serializers.auth import (
    RegisterSerializer, LoginSerializer, GoogleAuthSerializer,
    TokenResponseSerializer, RefreshTokenSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    VerifyEmailSerializer, UserSerializer, ProfileSerializer
)
from ..throttling import AuthRateThrottle, RegisterRateThrottle
from ..utils import success_response, error_response
from apps.core.models import Profile, EmailVerificationToken, PasswordResetToken

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """
    Registro de nuevo usuario (cliente o proveedor)
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                # Crear user - username es el mismo email
                user = User.objects.create_user(
                    username=data['email'],  # Username = email completo
                    email=data['email'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    password=data['password']
                )
                
                # Crear profile
                profile = Profile.objects.create(
                    user=user,
                    phone=data['phone'],
                    role=data['role'],
                    verified=False  # Requiere verificación
                )
                
                # Si es proveedor, crear ProviderProfile
                if data['role'] == 'provider':
                    from apps.core.models import ProviderProfile
                    ProviderProfile.objects.create(
                        user=user,
                        description='',
                        status='created',
                        registration_step=1
                    )
                
                # Crear token de verificación
                token = EmailVerificationToken.create_for_user(user, data['email'])
                
                # En desarrollo: auto-verificar email y no enviar correo
                if settings.DEBUG or getattr(settings, 'ENVIRONMENT', '') == 'development':
                    profile.verified = True
                    profile.save()
                    logger.info(f"🔧 [DEV] Email auto-verificado para {user.email}")
                else:
                    # Producción: enviar email de verificación (async)
                    from apps.core.tasks import send_verification_email_task
                    try:
                        # Construir URL de verificación
                        verification_url = f"https://app.liberi.com/verify-email?token={token.token}"
                        user_name = f"{user.first_name} {user.last_name}"
                        
                        send_verification_email_task.delay(
                            user.id,
                            user.email,
                            verification_url,
                            user_name
                        )
                    except Exception as e:
                        logger.error(f"Error enviando email de verificación: {e}")
                
                # Mensaje de éxito
                message = "Registro exitoso."
                if settings.DEBUG or getattr(settings, 'ENVIRONMENT', '') == 'development':
                    message = "Registro exitoso. Email auto-verificado (modo desarrollo)."
                else:
                    message = "Registro exitoso. Por favor verifica tu email."
                
                return success_response(
                    data={
                        'user_id': str(user.id),
                        'email': user.email,
                        'verified': profile.verified
                    },
                    message=message,
                    status_code=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return error_response(
                f"Error al crear usuario: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LoginView(APIView):
    """
    Login con email/username + password
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        username_or_email = data['username_or_email']
        password = data['password']
        
        # Intentar autenticar por email o username
        user = None
        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        else:
            user = authenticate(username=username_or_email, password=password)
        
        if user is None:
            return error_response(
                "Credenciales inválidas",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Verificar que el email esté verificado
        if not user.profile.verified:
            return error_response(
                "Email no verificado. Por favor verifica tu email antes de iniciar sesión.",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        # Preparar respuesta
        response_data = {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'expires_in': 86400,  # 24 horas
            'user': UserSerializer(user).data,
            'profile': ProfileSerializer(user.profile).data
        }
        
        return success_response(
            data=response_data,
            message="Login exitoso",
            status_code=status.HTTP_200_OK
        )


class GoogleAuthView(APIView):
    """
    Autenticación/Registro con Google OAuth
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Implementar verificación de Google ID Token
        # Por ahora retornamos error
        return error_response(
            "Google OAuth no implementado aún",
            status_code=status.HTTP_501_NOT_IMPLEMENTED
        )


class RefreshTokenView(APIView):
    """
    Refrescar access token usando refresh token
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(serializer.validated_data['refresh_token'])
            
            return success_response(
                data={
                    'access_token': str(refresh.access_token),
                    'expires_in': 86400
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return error_response(
                "Token inválido o expirado",
                status_code=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """
    Cerrar sesión (invalidar refresh token)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return success_response(
                message="Sesión cerrada exitosamente",
                status_code=status.HTTP_200_OK
            )
        except Exception:
            return success_response(
                message="Sesión cerrada",
                status_code=status.HTTP_200_OK
            )


class ForgotPasswordView(APIView):
    """
    Solicitar reset de contraseña
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            token = PasswordResetToken.create_for_user(user)
            
            # Enviar email (async)
            from apps.core.tasks import send_password_reset_email_task
            try:
                send_password_reset_email_task.delay(user.id, token.token)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando email de reset: {e}")
            
        except User.DoesNotExist:
            pass  # No revelar si el email existe
        
        return success_response(
            message="Si el email existe, recibirás instrucciones para resetear tu contraseña",
            status_code=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    """
    Resetear contraseña con token
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reset_token = PasswordResetToken.objects.get(
                token=serializer.validated_data['token']
            )
            
            if not reset_token.is_valid():
                return error_response(
                    "Token inválido o expirado",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Cambiar contraseña
            user = reset_token.user
            user.set_password(serializer.validated_data['password'])
            user.save()
            
            # Marcar token como usado
            reset_token.mark_as_used()
            
            return success_response(
                message="Contraseña actualizada exitosamente",
                status_code=status.HTTP_200_OK
            )
            
        except PasswordResetToken.DoesNotExist:
            return error_response(
                "Token inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )


class VerifyEmailView(APIView):
    """
    Verificar email con token
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_token = EmailVerificationToken.objects.get(
                token=serializer.validated_data['token']
            )
            
            if not verification_token.is_valid():
                return error_response(
                    "Token inválido o expirado",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Verificar email
            user = verification_token.user
            user.profile.verified = True
            user.profile.save()
            
            verification_token.verify()
            
            # Generar tokens para login automático
            refresh = RefreshToken.for_user(user)
            
            return success_response(
                data={
                    'access_token': str(refresh.access_token),
                    'refresh_token': str(refresh),
                    'expires_in': 86400,
                    'message': "Email verificado exitosamente"
                },
                status_code=status.HTTP_200_OK
            )
            
        except EmailVerificationToken.DoesNotExist:
            return error_response(
                "Token inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )


class ResendVerificationView(APIView):
    """
    Reenviar email de verificación
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.profile.verified:
            return error_response(
                "Email ya está verificado",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear nuevo token
        token = EmailVerificationToken.create_for_user(user, user.email)
        
        # Enviar email
        from apps.core.tasks import send_verification_email_task
        try:
            send_verification_email_task.delay(user.id, token.token)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error reenviando email de verificación: {e}")
        
        return success_response(
            message="Email de verificación enviado",
            status_code=status.HTTP_200_OK
        )
