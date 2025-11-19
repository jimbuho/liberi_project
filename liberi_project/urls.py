from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('', include('frontend.urls')),
    path('legal/', include('legal.urls')),
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = 'Liberi Admin'
admin.site.site_title = 'Liberi Admin Portal'
admin.site.index_title = 'Bienvenido al Panel de Administración'

handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'
handler400 = 'core.views.custom_400'
   
urlpatterns += [
    path('test-404/', views.test_404_view, name='test_404'),
    path('test-500/', views.test_500_view, name='test_500'),
    path('test-400/', views.test_400_view, name='test_400'),
]