from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'api_mobile'

# Router para ViewSets si los necesitamos
router = DefaultRouter()

urlpatterns = [
    # Incluir router
    path('', include(router.urls)),
    
    # URLs de autenticación
    path('auth/', include('apps.api_mobile.urls_auth')),
    
    # URLs de servicios públicos
    path('services/', include('apps.api_mobile.urls_services')),
    
    # URLs de proveedor
    path('provider/', include('apps.api_mobile.urls_provider')),
    
    # URLs de reservas
    path('bookings/', include('apps.api_mobile.urls_bookings')),
    
    # URLs de notif icaciones
    path('notifications/', include('apps.api_mobile.urls_notifications')),
]
