from django.shortcuts import redirect
from django.urls import resolve

from .models import LegalDocument, LegalAcceptance


class LegalAcceptanceMiddleware:
    """
    Middleware que verifica si un usuario autenticado ha aceptado
    los documentos legales requeridos según su rol.
    """
    
    EXEMPT_URLS = [
        'legal:document',
        'legal:accept',
        'legal:consent',
        'logout',
        'login',
        'home',
        'verify_email',
        'email_verification_pending_view',
        'provider_complete_profile_google',
        'customer_complete_profile_google',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # ✅ Si el usuario acaba de auto-aceptar términos con Google, no verificar
            if request.session.get('legal_auto_accepted', False):
                # Limpiar la flag después de la primera verificación
                if 'legal_auto_accepted' in request.session:
                    del request.session['legal_auto_accepted']
                response = self.get_response(request)
                return response
            
            try:
                resolved = resolve(request.path)
                view_name = resolved.url_name
                app_name = resolved.app_names[0] if resolved.app_names else None
                full_name = f"{app_name}:{view_name}" if app_name else view_name
                
                if view_name not in self.EXEMPT_URLS and full_name not in self.EXEMPT_URLS:
                    if not self._user_has_accepted_legal_documents(request.user):
                        return redirect('legal:consent')
            
            except Exception as e:
                pass
        
        response = self.get_response(request)
        return response
    
    def _user_has_accepted_legal_documents(self, user):
        """
        Verifica si el usuario ha aceptado todos los documentos requeridos
        según su rol
        """
        
        if not hasattr(user, 'profile'):
            return True
        
        user_role = user.profile.role
        
        if user_role == 'provider':
            required_docs = ['terms_provider', 'privacy_provider']
        else:
            required_docs = ['terms_user', 'privacy_user']
        
        for doc_type in required_docs:
            try:
                document = LegalDocument.objects.get(
                    document_type=doc_type,
                    is_active=True,
                    status='published'
                )
            except LegalDocument.DoesNotExist:
                continue
            
            if not LegalAcceptance.objects.filter(
                user=user,
                document=document
            ).exists():
                return False
        
        return True