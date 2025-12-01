from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    # Mostrar documento legal activo
    path('document/<str:document_type>/', views.legal_document_view, name='document'),
    
    # Rutas simplificadas
    path('terms/user/', views.legal_document_view, {'document_type': 'terms_user'}, name='terms_user'),
    path('privacy/user/', views.legal_document_view, {'document_type': 'privacy_user'}, name='privacy_user'),
    path('terms/provider/', views.legal_document_view, {'document_type': 'terms_provider'}, name='terms_provider'),
    path('privacy/provider/', views.legal_document_view, {'document_type': 'privacy_provider'}, name='privacy_provider'),
    
    # Aceptar documento (AJAX POST)
    path('accept/', views.accept_legal_document, name='accept'),
    
    # Página de consentimiento
    path('consent/', views.consent_view, name='consent'),
    
    # API para verificar aceptación
    path('api/check/<str:document_type>/', views.api_check_legal_acceptance, name='api_check'),
]