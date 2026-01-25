from django.urls import path
from .views import RegisterDeviceView, UnregisterDeviceView, SendTestNotificationView

app_name = 'push_notifications'

urlpatterns = [
    path('register/', RegisterDeviceView.as_view(), name='register'),
    path('unregister/', UnregisterDeviceView.as_view(), name='unregister'),
    path('test/', SendTestNotificationView.as_view(), name='test'),
]
