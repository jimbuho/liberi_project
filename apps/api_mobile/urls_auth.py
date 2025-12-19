from django.urls import path
from .views import auth as auth_views

urlpatterns = [
    path('register/', auth_views.RegisterView.as_view(), name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('google/', auth_views.GoogleAuthView.as_view(), name='google-auth'),
    path('refresh/', auth_views.RefreshTokenView.as_view(), name='refresh'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', auth_views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', auth_views.ResetPasswordView.as_view(), name='reset-password'),
    path('verify-email/', auth_views.VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', auth_views.ResendVerificationView.as_view(), name='resend-verification'),
]
