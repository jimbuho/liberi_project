from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError

from django.shortcuts import render

from .models import (
    Category, ProviderProfile, Service, Location, 
    Booking, Review, AuditLog
)

from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer, CategorySerializer,
    ProviderProfileSerializer, ServiceSerializer, LocationSerializer,
    BookingSerializer, ReviewSerializer
)
from .permissions import IsProviderOrReadOnly

def log_action(user, action, metadata=None):
    """Helper function to log actions"""
    AuditLog.objects.create(
        user=user,
        action=action,
        metadata=metadata or {}
    )


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        log_action(user, 'Usuario registrado', {'role': user.role})
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': '¡Registro exitoso! Bienvenido a Liberi.'
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        
        refresh = RefreshToken.for_user(user)
        
        log_action(user, 'Inicio de sesión')
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': f'¡Bienvenido de nuevo, {user.first_name or user.username}!'
        })


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class ProviderProfileViewSet(viewsets.ModelViewSet):
    queryset = ProviderProfile.objects.select_related('user', 'category')
    serializer_class = ProviderProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__username', 'description', 'category__name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__name__iexact=category)
        
        # Filter by zone
        zone = self.request.query_params.get('zone')
        if zone:
            queryset = queryset.filter(coverage_zones__contains=[zone])
        
        return queryset
    
    def create(self, request):
        if request.user.role != 'provider':
            return Response(
                {'error': 'Solo los proveedores pueden crear perfiles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if hasattr(request.user, 'provider_profile'):
            return Response(
                {'error': 'Ya tienes un perfil de proveedor'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        
        log_action(request.user, 'Perfil de proveedor creado')
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current provider's profile"""
        if not hasattr(request.user, 'provider_profile'):
            return Response(
                {'error': 'No tienes un perfil de proveedor'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(request.user.provider_profile)
        return Response(serializer.data)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related('provider').filter(available=True)
    serializer_class = ServiceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['base_price', 'created_at']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsProviderOrReadOnly()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(
                provider__provider_profile__category__name__iexact=category
            )
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(provider=self.request.user)
        log_action(self.request.user, 'Servicio creado', 
                  {'service_name': serializer.instance.name})


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Location.objects.filter(customer=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related('customer', 'provider', 'location')
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'customer':
            return Booking.objects.filter(customer=user)
        elif user.role == 'provider':
            return Booking.objects.filter(provider=user)
        return Booking.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
        log_action(self.request.user, 'Reserva creada')
    
    @action(detail=True, methods=['patch'])
    def accept(self, request, pk=None):
        booking = self.get_object()
        
        if booking.provider != request.user:
            return Response(
                {'error': 'No autorizado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'pending':
            return Response(
                {'error': 'Esta reserva ya no está pendiente'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'accepted'
        booking.save()
        
        log_action(request.user, 'Reserva aceptada', {'booking_id': str(booking.id)})
        
        return Response(BookingSerializer(booking).data)
    
    @action(detail=True, methods=['patch'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        
        if booking.provider != request.user:
            return Response(
                {'error': 'No autorizado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        booking.status = 'cancelled'
        booking.save()
        
        log_action(request.user, 'Reserva rechazada', {'booking_id': str(booking.id)})
        
        return Response(BookingSerializer(booking).data)
    
    @action(detail=True, methods=['patch'])
    def complete(self, request, pk=None):
        booking = self.get_object()
        
        if booking.provider != request.user:
            return Response(
                {'error': 'No autorizado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        booking.status = 'completed'
        booking.save()
        
        log_action(request.user, 'Reserva completada', {'booking_id': str(booking.id)})
        
        return Response(BookingSerializer(booking).data)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related('customer', 'booking')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by provider
        provider_id = self.request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(booking__provider_id=provider_id)
        
        return queryset
    
    def perform_create(self, serializer):
        booking = serializer.validated_data['booking']
        
        if booking.customer != self.request.user:
            raise ValidationError('No puedes reseñar esta reserva')
        
        serializer.save(customer=self.request.user)
        log_action(self.request.user, 'Reseña creada')

def custom_404(request, exception):
    """
    Vista personalizada para error 404 - Página no encontrada
    
    Se activa cuando:
    - El usuario intenta acceder a una URL que no existe
    - No hay coincidencia en los patrones de URL
    
    Args:
        request: HttpRequest object
        exception: La excepción que causó el 404
    
    Returns:
        HttpResponse con template 404.html y status 404
    """
    return render(request, '404.html', status=404)


def custom_500(request):
    """
    Vista personalizada para error 500 - Error del servidor
    
    Se activa cuando:
    - Hay una excepción no capturada en el código
    - Error en la base de datos
    - Error en las vistas o templates
    
    NOTA: Esta vista NO recibe 'exception' como parámetro
    
    Args:
        request: HttpRequest object
    
    Returns:
        HttpResponse con template 500.html y status 500
    """
    return render(request, '500.html', status=500)


def custom_400(request, exception):
    """
    Vista personalizada para error 400 - Solicitud incorrecta
    
    Se activa cuando:
    - Datos del formulario inválidos o malformados
    - Parámetros de URL incorrectos
    - Solicitud HTTP malformada
    
    Args:
        request: HttpRequest object
        exception: La excepción que causó el 400
    
    Returns:
        HttpResponse con template 400.html y status 400
    """
    return render(request, '400.html', status=400)


# ============================================
# OPCIONAL: VISTAS DE PRUEBA PARA TESTING
# ============================================

def test_404_view(request):
    """Vista de prueba para simular error 404"""
    from django.http import Http404
    raise Http404("Esta es una prueba de error 404")


def test_500_view(request):
    """Vista de prueba para simular error 500"""
    # Esto causará un error intencional
    raise Exception("Esta es una prueba de error 500")


def test_400_view(request):
    """Vista de prueba para simular error 400"""
    from django.http import HttpResponseBadRequest
    return HttpResponseBadRequest("Esta es una prueba de error 400")