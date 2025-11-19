# core/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

ALLOWED_UNVERIFIED_PATHS = [
    reverse('logout'),
    '/admin/',
    '/api/',
    '/static/',
    '/media/',
]

class PayPhoneReferrerPolicyMiddleware:
    """
    Middleware para asegurar que PayPhone reciba correctamente la información de referencia.
    CRÍTICO para que el botón de pago funcione.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Headers críticos para PayPhone
        response['Referrer-Policy'] = 'origin-when-cross-origin'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        
        return response


class EmailVerificationMiddleware:
    """Middleware que protege rutas para usuarios no verificados"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Si el usuario está autenticado
        if request.user.is_authenticated:
            # Verificar que su perfil esté verificado
            if hasattr(request.user, 'profile') and not request.user.profile.verified:
                # Si intenta acceder a una ruta protegida, redirigir
                if not self._is_allowed_path(request.path):
                    messages.warning(
                        request,
                        'Por favor, verifica tu email antes de acceder al sitio.'
                    )
                    return redirect('email_verification_pending_view')
        
        response = self.get_response(request)
        return response
    
    def _is_allowed_path(self, path):
        """Verifica si la ruta está permitida para usuarios no verificados"""
        for allowed_path in ALLOWED_UNVERIFIED_PATHS:
            if path.startswith(allowed_path) or path == allowed_path:
                return True
        return False
    
# core/middleware.py - Agregar esta clase

class ProviderProfileCheckMiddleware:
    """
    Middleware que verifica si un proveedor autenticado con Google
    necesita completar su perfil
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo verificar si el usuario está autenticado
        if request.user.is_authenticated:
            # Si es proveedor y no tiene provider_profile
            if (hasattr(request.user, 'profile') and 
                request.user.profile.role == 'provider' and 
                not hasattr(request.user, 'provider_profile')):
                
                # Permitir acceso a estas rutas
                allowed_paths = [
                    '/provider/complete-profile-google/',
                    '/logout/',
                    '/accounts/logout/',
                    '/static/',
                    '/media/',
                ]
                
                # Si no está en una ruta permitida, redirigir
                if not any(request.path.startswith(path) for path in allowed_paths):
                    from django.shortcuts import redirect
                    return redirect('complete_provider_profile_google')
        
        response = self.get_response(request)
        return response