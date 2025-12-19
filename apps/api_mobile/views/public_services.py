from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework import status

from ..serializers.services import (
    CategorySerializer, ServiceListSerializer, ServiceDetailSerializer
)
from ..serializers.auth import CitySerializer
from ..utils import success_response, error_response, paginated_response
from apps.core.models import Category, Service, City, Zone


class CategoryListView(APIView):
    """
    GET /api/v1/services/categories/
    
    Listar categorías disponibles
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        categories = Category.objects.filter(active=True).order_by('name')
        serializer = CategorySerializer(categories, many=True)
        return success_response(data=serializer.data)


class CityListView(APIView):
    """
    GET /api/v1/services/cities/
    
    Listar ciudades disponibles
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        cities = City.objects.filter(active=True).order_by('name')
        serializer = CitySerializer(cities, many=True)
        return success_response(data=serializer.data)


class ZoneListView(APIView):
    """
    GET /api/v1/services/zones/
    
    Listar zonas por ciudad
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        city_id = request.query_params.get('city_id')
        
        zones = Zone.objects.filter(active=True)
        
        if city_id:
            zones = zones.filter(city_id=city_id)
        
        zones = zones.select_related('city').order_by('city__name', 'name')
        
        from ..serializers.services import ZoneSerializer
        serializer = ZoneSerializer(zones, many=True)
        return success_response(data=serializer.data)


class ServiceListView(APIView):
    """
    GET /api/v1/services/
    
    Listar servicios disponibles con filtros
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Filtros
        category_id = request.query_params.get('category')
        city_id = request.query_params.get('city')
        zone_id = request.query_params.get('zone')
        search = request.query_params.get('search')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        
        # Query base: solo servicios disponibles de proveedores aprobados
        services = Service.objects.filter(
            available=True,
            provider__provider_profile__status='approved',
            provider__provider_profile__is_active=True
        ).select_related(
            'provider__provider_profile',
            'provider__provider_profile__category'
        ).order_by('-created_at')
        
        # Aplicar filtros
        if category_id:
            services = services.filter(
                provider__provider_profile__category_id=category_id
            )
        
        if search:
            from django.db.models import Q
            services = services.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(provider__provider_profile__business_name__icontains=search)
            )
        
        if min_price:
            services = services.filter(base_price__gte=min_price)
        
        if max_price:
            services = services.filter(base_price__lte=max_price)
        
        # TODO: Filtrar por zona (requiere calcular distancias)
        
        # Serializar con paginación
        return paginated_response(
            services,
            ServiceListSerializer,
            request
        )


class ServiceDetailView(APIView):
    """
    GET /api/v1/services/{service_code}/
    
    Detalle de un servicio
    """
    permission_classes = [AllowAny]
    
    def get(self, request, service_code):
        try:
            service = Service.objects.select_related(
                'provider__provider_profile',
                'provider__provider_profile__category'
            ).get(
                service_code=service_code,
                available=True
            )
        except Service.DoesNotExist:
            return error_response(
                "Servicio no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ServiceDetailSerializer(service, context={'request': request})
        return success_response(data=serializer.data)
