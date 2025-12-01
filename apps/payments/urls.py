from django.urls import path
from .views import CreatePaymentView, VerifyPaymentView, BankTransferView

urlpatterns = [
    path('payphone/create/', CreatePaymentView.as_view(), name='create-payment'),
    path('payphone/verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('bank-transfer/', BankTransferView.as_view(), name='bank-transfer'),
]
