from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a los dueños editar objetos.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Verificar si el objeto tiene atributo customer o provider
        if hasattr(obj, 'customer'):
            return obj.customer == request.user
        if hasattr(obj, 'provider'):
            return obj.provider == request.user
        
        return False


class IsProviderOrReadOnly(permissions.BasePermission):
    """
    Permiso que solo permite a proveedores crear/editar.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'provider'
