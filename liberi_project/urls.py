from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
import os

from apps.core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.core.urls')),
    path('api/messaging/', include('apps.messaging.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('OneSignalSDKWorker.js', serve, {'path': 'OneSignalSDKWorker.js', 'document_root': os.path.join(settings.BASE_DIR, 'static')}),
    
    # Mobile API v1
    path('api/v1/', include('apps.api_mobile.urls', namespace='api_mobile')),

    # Onesignal
    path('api/push/', include('apps.push_notifications.urls')),
    
    # New refactored apps
    path('', include('apps.authentication.urls')),
    path('', include('apps.profiles.urls')),
    path('', include('apps.bookings.urls')),
    path('', include('apps.payments.urls')),
    path('', include('apps.public.urls')),
    
    path('', include('apps.frontend.urls')),
    path('legal/', include('apps.legal.urls')),
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = 'Liberi Admin'
admin.site.site_title = 'Liberi Admin Portal'
admin.site.index_title = 'Bienvenido al Panel de Administración'

handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'
handler400 = 'apps.core.views.custom_400'
   
urlpatterns += [
    path('test-404/', views.test_404_view, name='test_404'),
    path('test-500/', views.test_500_view, name='test_500'),
    path('test-400/', views.test_400_view, name='test_400'),
]