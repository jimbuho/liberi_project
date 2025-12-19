from django.urls import path
from .views import provider as provider_views
from .views import provider_bookings as bookings_views
from .views import provider_locations as locations_views
from .views import provider_withdrawals as withdrawals_views

urlpatterns = [
    # Dashboard
    path('dashboard/', provider_views.DashboardView.as_view(), name='provider-dashboard'),
    
    # Perfil
    path('profile/', provider_views.ProfileView.as_view(), name='provider-profile'),
    
    # Servicios
    path('services/', provider_views.ServiceListCreateView.as_view(), name='provider-services'),
    path('services/<int:service_id>/', provider_views.ServiceDetailView.as_view(), name='provider-service-detail'),
    
    # Reservas
    path('bookings/', bookings_views.ProviderBookingListView.as_view(), name='provider-bookings'),
    path('bookings/<uuid:booking_id>/accept/', bookings_views.BookingAcceptView.as_view(), name='provider-booking-accept'),
    path('bookings/<uuid:booking_id>/reject/', bookings_views.BookingRejectView.as_view(), name='provider-booking-reject'),
    path('bookings/<uuid:booking_id>/complete-with-code/', bookings_views.BookingCompleteWithCodeView.as_view(), name='provider-booking-complete'),
    
    # Verificación
    path('verification/documents/', bookings_views.VerificationDocumentsView.as_view(), name='provider-verification-docs'),
    path('verification/request-reverification/', bookings_views.RequestReverificationView.as_view(), name='provider-reverification'),
    
    # Ubicaciones
    path('locations/', locations_views.LocationListCreateView.as_view(), name='provider-locations'),
    path('locations/<int:location_id>/', locations_views.LocationDetailView.as_view(), name='provider-location-detail'),
    path('service-mode/', locations_views.ServiceModeView.as_view(), name='provider-service-mode'),
    
    # Cobertura y Costos
    path('coverage/', locations_views.CoverageListView.as_view(), name='provider-coverage'),
    path('coverage/<int:zone_id>/', locations_views.CoverageDetailView.as_view(), name='provider-coverage-detail'),
    path('zone-costs/<int:zone_id>/', locations_views.ZoneCostView.as_view(), name='provider-zone-cost'),
    
    # Horarios
    path('schedule/', locations_views.ScheduleListCreateView.as_view(), name='provider-schedule'),
    path('schedule/<int:schedule_id>/', locations_views.ScheduleDetailView.as_view(), name='provider-schedule-detail'),
    path('unavailability/', locations_views.UnavailabilityListCreateView.as_view(), name='provider-unavailability'),
    path('unavailability/<int:unavailability_id>/', locations_views.UnavailabilityDetailView.as_view(), name='provider-unavailability-detail'),
    
    # Cuentas Bancarias
    path('banks/', withdrawals_views.BankListView.as_view(), name='provider-banks'),
    path('bank-accounts/', withdrawals_views.BankAccountListCreateView.as_view(), name='provider-bank-accounts'),
    path('bank-accounts/<uuid:account_id>/', withdrawals_views.BankAccountDetailView.as_view(), name='provider-bank-account-detail'),
    
    # Retiros
    path('withdrawals/', withdrawals_views.WithdrawalListView.as_view(), name='provider-withdrawals'),
    path('withdrawals/create/', withdrawals_views.WithdrawalCreateView.as_view(), name='provider-withdrawal-create'),
    
    # Toggle Active
    path('toggle-active/', locations_views.ToggleActiveView.as_view(), name='provider-toggle-active'),
]
