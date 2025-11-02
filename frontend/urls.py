from django.urls import path
from . import views

urlpatterns = [
    # Home & Public
    path('', views.home, name='home'),
    path('services/', views.services_list, name='services_list'),
    path('services/<int:service_id>/', views.service_detail, name='service_detail'),
    path('providers/', views.providers_list, name='providers_list'),
    path('providers/<int:provider_id>/', views.provider_profile, name='provider_profile'),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register/provider/', views.register_provider_view, name='register_provider'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Bookings
    path('bookings/', views.bookings_list, name='bookings_list'),
    path('bookings/<uuid:booking_id>/', views.booking_detail, name='booking_detail'),
    path('bookings/create/', views.booking_create, name='booking_create'),
    path('bookings/<uuid:booking_id>/accept/', views.booking_accept, name='booking_accept'),
    path('bookings/<uuid:booking_id>/reject/', views.booking_reject, name='booking_reject'),
    path('bookings/<uuid:booking_id>/complete/', views.booking_complete, name='booking_complete'),
    
    # Locations
    path('locations/create/', views.location_create, name='location_create'),
    path('locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),
    
    # Reviews
    path('bookings/<uuid:booking_id>/review/', views.review_create, name='review_create'),
    
    # Service Management (Provider)
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:service_id>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:service_id>/delete/', views.service_delete, name='service_delete'),

    # Booking con horarios
    path('bookings/create/<int:service_id>/', views.booking_create_step1, name='booking_create_step1'),
    
    # Provider Schedule Management
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
    path('api/detect-location/', views.detect_user_location, name='detect_location'),

    # Pagos v2 (con imagen)
    path('payments/<uuid:booking_id>/', views.payment_process, name='payment_process'),
    path('payments/payphone/create/', views.payphone_create, name='payphone_create'),
    path('payments/bank-transfer/', views.bank_transfer, name='bank_transfer'),
    path('payments/v2/<uuid:booking_id>/', views.payment_process_v2, name='payment_process_v2'),
    path('payments/bank-transfer-v2/', views.bank_transfer_v2, name='bank_transfer_v2'),

    # API de Notificaciones
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]