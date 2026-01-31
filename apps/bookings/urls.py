from django.urls import path
from . import views

urlpatterns = [
    path('bookings/', views.bookings_list, name='bookings_list'),
    
    # Specific paths MUST come before generic <str:booking_id>
    path('bookings/create/step1/<int:service_id>/', views.booking_create_step1, name='booking_create_step1'),
    path('bookings/create/', views.booking_create, name='booking_create'),
    
    # Generic path
    path('bookings/<str:booking_id>/', views.booking_detail, name='booking_detail'),
    
    path('bookings/<uuid:booking_id>/accept/', views.booking_accept, name='booking_accept'),
    path('bookings/<uuid:booking_id>/reject/', views.booking_reject, name='booking_reject'),
    path('bookings/<uuid:booking_id>/cancel/', views.booking_cancel, name='booking_cancel'),
    path('bookings/<uuid:booking_id>/complete/', views.booking_complete, name='booking_complete'),
    path('bookings/<uuid:booking_id>/complete-code/', views.booking_complete_with_code, name='booking_complete_with_code'),
    path('bookings/<uuid:booking_id>/report-incident/', views.booking_report_incident, name='booking_report_incident'),
]
