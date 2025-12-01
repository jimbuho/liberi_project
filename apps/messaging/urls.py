from django.urls import path
from .views import SendWhatsAppView

urlpatterns = [
    path('whatsapp/send/', SendWhatsAppView.as_view(), name='send-whatsapp'),
]
