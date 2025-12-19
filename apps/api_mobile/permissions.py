from rest_framework import permissions


class IsProvider(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol provider
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.role == 'provider'


class IsCustomer(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol customer
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.role == 'customer'


class IsVerifiedProvider(permissions.BasePermission):
    """
    Permite acceso solo a proveedores verificados (status=approved)
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'profile'):
            return False
        if request.user.profile.role != 'provider':
            return False
        if not hasattr(request.user, 'provider_profile'):
            return False
        return request.user.provider_profile.status == 'approved'


class IsEmailVerified(permissions.BasePermission):
    """
    Verifica que el email del usuario esté verificado
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'profile') and request.user.profile.verified


class IsBookingParticipant(permissions.BasePermission):
    """
    Permite acceso solo al cliente o proveedor de la reserva
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.customer == request.user or obj.provider == request.user
