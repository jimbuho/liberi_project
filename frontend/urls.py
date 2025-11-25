from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Home & Public
    path('', views.home, name='home'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register/provider/', views.register_provider_view, name='register_provider'),
    path('register/provider/step2/', views.provider_register_step2, name='provider_register_step2'),
    path('logout/', views.logout_view, name='logout'),

    # urls.py
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('email-verification-pending/', views.email_verification_pending, name='email_verification_pending_view'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Bookings
    path('bookings/', views.bookings_list, name='bookings_list'),
    path('bookings/create/', views.booking_create, name='booking_create'),
    path('bookings/<str:booking_id>/', views.booking_detail, name='booking_detail'),
    path('bookings/<uuid:booking_id>/accept/', views.booking_accept, name='booking_accept'),
    path('bookings/<uuid:booking_id>/reject/', views.booking_reject, name='booking_reject'),
    path('bookings/<uuid:booking_id>/complete/', views.booking_complete, name='booking_complete'),
    path('bookings/<int:booking_id>/payment/', views.payment_process, name='payment_process'),
    path('bookings/<uuid:booking_id>/complete-with-code/', views.booking_complete_with_code, name='booking_complete_with_code'),
    path('bookings/<uuid:booking_id>/report-incident/', views.booking_report_incident, name='booking_report_incident'),
    
    # Locations
    path('locations/create/', views.location_create, name='location_create'),
    path('locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),
    
    # Reviews
    path('bookings/<uuid:booking_id>/review/', views.review_create, name='review_create'),
    
    # Service Management (Provider)
    path('services/', views.services_list, name='services_list'),
    path('services/<uuid:service_code>/', views.service_detail, name='service_detail'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:service_id>/edit/', views.service_edit, name='service_edit'),  # Mantener ID para edición (admin)
    path('services/<int:service_id>/delete/', views.service_delete, name='service_delete'),  # Mantener ID para eliminación (admin)

    # Booking con horarios
    path('bookings/create/<int:service_id>/', views.booking_create_step1, name='booking_create_step1'),
    
    # Provider Schedule Management
    path('providers/', views.providers_list, name='providers_list'),
    path('providers/<slug:slug>/', views.provider_profile, name='provider_profile'),
    path('provider/profile/edit/', views.provider_profile_edit, name='provider_profile_edit'),
    path('provider/schedules/', views.provider_schedule_manage, name='provider_schedule_manage'),
    path('provider/schedules/create/', views.provider_schedule_create, name='provider_schedule_create'),
    path('provider/schedules/<int:schedule_id>/delete/', views.provider_schedule_delete, name='provider_schedule_delete'),
    
    # Provider Unavailability Management
    path('provider/unavailability/', views.provider_unavailability_manage, name='provider_unavailability_manage'),
    path('provider/unavailability/create/', views.provider_unavailability_create, name='provider_unavailability_create'),
    path('provider/unavailability/<int:unavailability_id>/delete/', views.provider_unavailability_delete, name='provider_unavailability_delete'),

    # Provider Coverage Management (NUEVO)
    path('provider/coverage/', views.provider_coverage_manage, name='provider_coverage_manage'),
    path('provider/coverage/add/', views.provider_coverage_add, name='provider_coverage_add'),
    path('provider/coverage/<int:zone_id>/remove/', views.provider_coverage_remove, name='provider_coverage_remove'),
    
    # Provider Toggle Active
    path('provider/toggle-active/', views.provider_toggle_active, name='provider_toggle_active'),

     # Zone Costs Management
    path('provider/zone-costs/', views.provider_zone_costs_manage, name='provider_zone_costs_manage'),
    path('provider/zone-costs/update/', views.provider_zone_cost_update, name='provider_zone_cost_update'),
    path('provider/zone-costs/<int:zone_id>/delete/', views.provider_zone_cost_delete, name='provider_zone_cost_delete'),
    
    # Location Detection & Zone Selection
    path('api/set-zone/', views.set_current_zone, name='set_current_zone'),
    path('api/set-city/', views.set_current_city_ajax, name='set_current_city'),  # ← AGREGAR ESTA
    path('api/detect-location/', views.detect_user_location, name='detect_location'),

    # Pagos v2 (con imagen)
    path('payments/<uuid:booking_id>/', views.payment_process, name='payment_process'),
    path('payments/payphone/callback/', views.payphone_callback, name='payphone_callback'),
    
    path('payment/bank-transfer/<uuid:booking_id>/', views.payment_bank_transfer, name='payment_bank_transfer'),
    path('payment/confirm-transfer/<uuid:booking_id>/', views.confirm_bank_transfer_payment, name='confirm_bank_transfer'),
    path('payment/confirmation/<int:payment_id>/', views.payment_confirmation, name='payment_confirmation'),

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

    # Password Reset
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),
    path('change-password/', views.change_password_view, name='change_password'),

    # Google OAuth para proveedores
    path('auth/google/provider/', views.google_provider_signup, name='google_provider_signup'),
    path('provider/complete-profile-google/', views.complete_provider_profile_google, name='complete_provider_profile_google'),

    # Provider Location Management
    path('provider/locations/', views.provider_locations_list, name='provider_locations_list'),
    path('provider/locations/create/', views.provider_location_create, name='provider_location_create'),
    path('provider/locations/create/base/', lambda r: views.provider_location_create(r, loc_type='base'), name='provider_location_create_base'),
    path('provider/locations/create/local/', lambda r: views.provider_location_create(r, loc_type='local'), name='provider_location_create_local'),
    path('provider/locations/<int:loc_id>/edit/', views.provider_location_edit, name='provider_location_edit'),
    path('provider/locations/<int:loc_id>/delete/', views.provider_location_delete, name='provider_location_delete'),
    path('provider/settings/service-mode/', views.provider_settings_service_mode, name='provider_settings_service_mode'),
    path('api/zones-by-city/', views.api_get_zones_by_city, name='api_get_zones_by_city'),
    path('api/service-locations/', views.api_get_service_locations, name='api_get_service_locations'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)