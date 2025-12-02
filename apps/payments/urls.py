from django.urls import path
from . import views

urlpatterns = [
    # ============================================
    # API Routes (Preserving /api/payments/ prefix)
    # ============================================
    path('api/payments/payphone/create/', views.CreatePaymentView.as_view(), name='create-payment'),
    path('api/payments/payphone/verify/', views.VerifyPaymentView.as_view(), name='verify-payment'),
    path('api/payments/bank-transfer/', views.BankTransferView.as_view(), name='bank-transfer-api'),
    
    # ============================================
    # Template Views (New - From frontend)
    # ============================================
    path('payments/<uuid:booking_id>/', views.payment_process, name='payment_process'),
    path('payments/<uuid:booking_id>/bank-transfer/', views.payment_bank_transfer, name='payment_bank_transfer'),
    path('payments/<uuid:booking_id>/confirm-transfer/', views.confirm_bank_transfer_payment, name='confirm_bank_transfer_payment'),
    path('payments/confirmation/<int:payment_id>/', views.payment_confirmation, name='payment_confirmation'),
    
    # ============================================
    # Webhooks (New)
    # ============================================
    path('payments/payphone/callback/', views.payphone_callback, name='payphone_callback'),
]
