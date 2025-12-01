from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, LoginView, CategoryViewSet, ProviderProfileViewSet,
    ServiceViewSet, LocationViewSet, BookingViewSet, ReviewViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'providers', ProviderProfileViewSet, basename='provider')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
