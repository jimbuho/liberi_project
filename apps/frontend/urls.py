from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Home & Public
    path('', views.home, name='home'),

    # Service Management (Provider)
    path('services/create/', views.service_create, name='service_create'),  # Debe estar ANTES de la ruta dinámica
    path('services/<int:service_id>/edit/', views.service_edit, name='service_edit'),  # Mantener ID para edición (admin)
    path('services/<int:service_id>/delete/', views.service_delete, name='service_delete'),  # Mantener ID para eliminación (admin)
 
    # Location Detection & Zone Selection
    path('api/set-zone/', views.set_current_zone, name='set_current_zone'),
    path('api/set-city/', views.set_current_city_ajax, name='set_current_city'),  # ← AGREGAR ESTA
    path('api/detect-location/', views.detect_user_location, name='detect_location'),

     # Locations
    path('locations/create/', views.location_create, name='location_create'),
    path('locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),

    # Reviews
    path('bookings/<uuid:booking_id>/review/', views.review_create, name='review_create'),
    
    # Pagos v2 (con imagen)
    path('payments/<uuid:booking_id>/', views.payment_process, name='payment_process'),
    path('payments/payphone/callback/', views.payphone_callback, name='payphone_callback'),
    
    path('payment/bank-transfer/<uuid:booking_id>/', views.payment_bank_transfer, name='payment_bank_transfer'),
    path('payment/confirm-transfer/<uuid:booking_id>/', views.confirm_bank_transfer_payment, name='confirm_bank_transfer'),
    path('payment/confirmation/<int:payment_id>/', views.payment_confirmation, name='service_create'),

    # API de Notificaciones
    path('api/notifications/', views.api_notifications_list, name='api_notifications_list'),
    path('api/notifications/count/', views.api_notifications_count, name='api_notifications_count'),
    path('api/notifications/<int:notification_id>/mark-read/', views.api_notification_mark_read, name='api_notification_mark_read'),
    path('api/notifications/mark-all-read/', views.api_notifications_mark_all_read, name='api_notifications_mark_all_read'),

    # Retiros y cuentas bancarias
    path('provider/bank-accounts/', views.provider_bank_accounts, name='provider_bank_accounts'),
    path('provider/bank-accounts/<uuid:account_id>/delete/', views.provider_bank_account_delete, name='provider_bank_account_delete'),
    path('provider/withdrawals/', views.provider_withdrawal_list, name='provider_withdrawal_list'),
    path('provider/withdrawals/create/', views.provider_withdrawal_create, name='provider_withdrawal_create'),

    # Provider Location Management
    path('provider/locations/create/base/', lambda r: views.provider_location_create(r, loc_type='base'), name='provider_location_create_base'),
    path('provider/locations/create/local/', lambda r: views.provider_location_create(r, loc_type='local'), name='provider_location_create_local'),
    path('api/zones-by-city/', views.api_get_zones_by_city, name='api_get_zones_by_city'),
    path('api/service-locations/', views.api_get_service_locations, name='api_get_service_locations'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)