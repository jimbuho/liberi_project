from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.conf import settings


class AuthRateThrottle(AnonRateThrottle):
    """
    Throttle para endpoints de autenticación
    DESHABILITADO en desarrollo
    """
    rate = '10/hour'
    scope = 'auth'
    
    def allow_request(self, request, view):
        # Deshabilitar throttling en desarrollo
        if settings.DEBUG or getattr(settings, 'ENVIRONMENT', '') == 'development':
            return True
        return super().allow_request(request, view)


class RegisterRateThrottle(AnonRateThrottle):
    """
    Throttle para registro
    DESHABILITADO en desarrollo
    """
    rate = '3/hour'
    scope = 'register'
    
    def allow_request(self, request, view):
        # Deshabilitar throttling en desarrollo
        if settings.DEBUG or getattr(settings, 'ENVIRONMENT', '') == 'development':
            return True
        return super().allow_request(request, view)


class PaymentRateThrottle(UserRateThrottle):
    """
    Limita operaciones de pago por usuario autenticado
    """
    rate = '10/minute'
    scope = 'payments'


class WithdrawalRateThrottle(UserRateThrottle):
    """
    Limita solicitudes de retiro por usuario
    """
    rate = '3/day'
    scope = 'withdrawals'
