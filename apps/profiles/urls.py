from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/customer/', views.dashboard_customer, name='dashboard_customer'),
    path('dashboard/provider/', views.dashboard_provider, name='dashboard_provider'),
    
    # NUEVO: Settings unificado
    path('provider/settings/', views.provider_settings, name='provider_settings'),
    
    path('provider/profile/edit/', views.provider_profile_edit, name='provider_profile_edit'),
    path('provider/settings/service-mode/', views.provider_settings_service_mode, name='provider_settings_service_mode'),
    path('provider/toggle-active/', views.provider_toggle_active, name='provider_toggle_active'),
    
    # Locations
    path('provider/locations/', views.provider_locations_list, name='provider_locations_list'),
    path('provider/locations/create/<str:loc_type>/', views.provider_location_create, name='provider_location_create'),
    path('provider/locations/edit/<int:loc_id>/', views.provider_location_edit, name='provider_location_edit'),
    path('provider/locations/delete/<int:loc_id>/', views.provider_location_delete, name='provider_location_delete'),
    
    # Schedule
    path('provider/schedule/', views.provider_schedule_manage, name='provider_schedule_manage'),
    path('provider/schedule/create/', views.provider_schedule_create, name='provider_schedule_create'),
    path('provider/schedule/delete/<int:schedule_id>/', views.provider_schedule_delete, name='provider_schedule_delete'),
    
    # Unavailability
    path('provider/unavailability/', views.provider_unavailability_manage, name='provider_unavailability_manage'),
    path('provider/unavailability/create/', views.provider_unavailability_create, name='provider_unavailability_create'),
    path('provider/unavailability/delete/<int:unavailability_id>/', views.provider_unavailability_delete, name='provider_unavailability_delete'),
    
    # Zone Costs
    path('provider/zone-costs/', views.provider_zone_costs_manage, name='provider_zone_costs_manage'),
    path('provider/zone-costs/update/', views.provider_zone_cost_update, name='provider_zone_cost_update'),
    path('provider/zone-costs/delete/<int:zone_id>/', views.provider_zone_cost_delete, name='provider_zone_cost_delete'),
    
    # Coverage
    path('provider/coverage/', views.provider_coverage_manage, name='provider_coverage_manage'),
    path('provider/coverage/add/', views.provider_coverage_add, name='provider_coverage_add'),
    path('provider/coverage/remove/<int:zone_id>/', views.provider_coverage_remove, name='provider_coverage_remove'),
]