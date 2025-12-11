from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services/', views.services_list, name='services_list'),
    path('services/<uuid:service_code>/', views.service_detail, name='service_detail'),
    path('providers/<slug:slug>/', views.provider_profile, name='provider_profile'),
    
    # Landing pages
    path('social/categorias/', views.landing_categories, name='landing_categories'),
    
    # AJAX endpoints
    path('ajax/set-city/', views.set_current_city_ajax, name='set_current_city_ajax'),
    path('ajax/set-zone/', views.set_current_zone, name='set_current_zone'),
    path('ajax/detect-location/', views.detect_user_location, name='detect_user_location'),
]
