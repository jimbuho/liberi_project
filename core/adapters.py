# core/adapters.py - VERSIÓN COMPLETA Y CORREGIDA

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.shortcuts import redirect
from core.models import Profile
from legal.models import LegalDocument, LegalAcceptance
import logging

logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter personalizado para conectar cuentas sociales con cuentas existentes
    basándose en el email
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Se ejecuta antes de que se complete el login social
        Conecta la cuenta social con una cuenta existente si el email coincide
        """
        # Si el usuario ya está autenticado, no hacer nada
        if sociallogin.is_existing:
            return
        
        # Obtener el email de la cuenta social
        email = None
        if sociallogin.account.provider == 'google':
            email = sociallogin.account.extra_data.get('email')
        
        if not email:
            return
        
        # Buscar si existe un usuario con ese email
        try:
            user = User.objects.get(email=email)
            
            # Conectar la cuenta social con el usuario existente
            sociallogin.connect(request, user)
            
            # Marcar como verificado si no lo está
            if hasattr(user, 'profile') and not user.profile.verified:
                user.profile.verified = True
                user.profile.save()
            
            # Activar usuario si no está activo
            if not user.is_active:
                user.is_active = True
                user.save()
                
        except User.DoesNotExist:
            # No existe usuario con ese email, continuar con el registro normal
            pass
    
    def save_user(self, request, sociallogin, form=None):
        """
        Se ejecuta al crear un nuevo usuario desde login social
        """
        user = super().save_user(request, sociallogin, form)
        
        # Determinar el rol basado en el parámetro de sesión
        is_provider_signup = request.session.get('is_provider_signup', False)
        role = 'provider' if is_provider_signup else 'customer'
        
        logger.info(f"Creando usuario desde Google: {user.email}, rol: {role}")
        
        # Asegurarse de que el perfil exista y esté verificado
        if hasattr(user, 'profile'):
            user.profile.verified = True
            user.profile.role = role
            user.profile.save()
        else:
            # Crear perfil si no existe
            Profile.objects.create(
                user=user,
                phone='',  # Se pedirá después
                role=role,
                verified=True  # Auto-verificado por Google
            )
        
        # ✅ AUTO-ACEPTAR TÉRMINOS LEGALES
        self._auto_accept_legal_terms(request, user, role)
        
        # ✅ MARCAR EN SESIÓN QUE YA ACEPTÓ TÉRMINOS (para evitar loop con middleware)
        request.session['legal_auto_accepted'] = True
        
        # Si es proveedor, marcar que necesita completar perfil
        if is_provider_signup:
            request.session['needs_provider_profile'] = True
            logger.info(f"Usuario {user.email} necesita completar perfil de proveedor")
        
        # Limpiar flag de sesión
        if 'is_provider_signup' in request.session:
            del request.session['is_provider_signup']
        
        # Asegurarse de que el usuario está activo
        if not user.is_active:
            user.is_active = True
            user.save()
        
        return user
    
    def _auto_accept_legal_terms(self, request, user, role):
        """
        Auto-acepta los términos legales para usuarios registrados con Google
        """
        from legal.views import get_client_ip, get_user_agent
        
        # Determinar qué documentos necesita según el rol
        if role == 'provider':
            doc_types = ['terms_provider', 'privacy_provider']
        else:
            doc_types = ['terms_user', 'privacy_user']
        
        for doc_type in doc_types:
            try:
                document = LegalDocument.objects.get(
                    document_type=doc_type,
                    is_active=True,
                    status='published'
                )
                
                # Crear aceptación automática
                LegalAcceptance.objects.get_or_create(
                    user=user,
                    document=document,
                    defaults={
                        'ip_address': get_client_ip(request),
                        'user_agent': get_user_agent(request),
                        'accepted_via': 'google_oauth'
                    }
                )
                logger.info(f"Auto-aceptado {doc_type} para {user.email}")
                
            except LegalDocument.DoesNotExist:
                logger.warning(f"Documento legal {doc_type} no encontrado")
                continue
    
    def get_login_redirect_url(self, request):
        """
        Determina a dónde redirigir después del login con Google
        """
        # Si necesita completar perfil de proveedor
        if request.session.get('needs_provider_profile', False):
            logger.info("Redirigiendo a completar perfil de proveedor")
            if 'needs_provider_profile' in request.session:
                del request.session['needs_provider_profile']
            return '/provider/complete-profile-google/'
        
        # Si el usuario ya tiene perfil de proveedor pero está incompleto
        if hasattr(request.user, 'profile') and request.user.profile.role == 'provider':
            if not hasattr(request.user, 'provider_profile'):
                logger.info("Usuario es proveedor pero no tiene ProviderProfile")
                return '/provider/complete-profile-google/'
        
        # Redirigir al dashboard normal
        logger.info("Redirigiendo al dashboard")
        return '/dashboard/'