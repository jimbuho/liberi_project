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