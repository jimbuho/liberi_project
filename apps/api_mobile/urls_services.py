from django.urls import path
from .views import public_services

urlpatterns = [
    # Categorías
    path('categories/', public_services.CategoryListView.as_view(), name='categories-list'),
    
    # Ciudades
    path('cities/', public_services.CityListView.as_view(), name='cities-list'),
    
    # Zonas
    path('zones/', public_services.ZoneListView.as_view(), name='zones-list'),
    
    # Servicios
    path('', public_services.ServiceListView.as_view(), name='services-list'),
    path('<str:service_code>/', public_services.ServiceDetailView.as_view(), name='service-detail'),
]
