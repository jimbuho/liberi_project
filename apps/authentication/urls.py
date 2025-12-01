from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register/provider/', views.register_provider_view, name='register_provider'),
    path('register/provider/step2/', views.provider_register_step2, name='provider_register_step2'),
    path('logout/', views.logout_view, name='logout'),
    
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('email-verification-pending/', views.email_verification_pending, name='email_verification_pending_view'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    path('auth/google/provider/', views.google_provider_signup, name='google_provider_signup'),
    path('provider/complete-profile-google/', views.complete_provider_profile_google, name='complete_provider_profile_google'),
]
