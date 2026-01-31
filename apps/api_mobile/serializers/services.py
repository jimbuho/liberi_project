from rest_framework import serializers
from apps.core.models import (
    Service, Category, ProviderProfile, 
    Review, Zone, City
)


class CategorySerializer(serializers.ModelSerializer):
    """Serializer para Categoría"""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'icon']


class ZoneSerializer(serializers.ModelSerializer):
    """Serializer para Zona"""
    city = serializers.StringRelatedField()
    city_id = serializers.IntegerField(source='city.id', read_only=True)
    
    class Meta:
        model = Zone
        fields = ['id', 'name', 'city', 'city_id']


class ProviderPublicSerializer(serializers.ModelSerializer):
    """Serializer público del proveedor (para listado de servicios)"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProviderProfile
        fields = [
            'slug', 'business_name', 'profile_photo', 'description',
            'category_name', 'user_name', 'rating', 'reviews_count',
            'service_mode'
        ]
    
    def get_rating(self, obj):
        from django.db.models import Avg
        result = Review.objects.filter(
            booking__provider=obj.user
        ).aggregate(avg=Avg('rating'))
        return round(result['avg'] or 0, 1)
    
    def get_reviews_count(self, obj):
        return Review.objects.filter(booking__provider=obj.user).count()


class ServiceListSerializer(serializers.ModelSerializer):
    """Serializer para listado de servicios (vista cliente)"""
    provider = ProviderPublicSerializer(source='provider.provider_profile', read_only=True)
    primary_image = serializers.SerializerMethodField()
    travel_cost = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True, default=0,
        help_text='Costo de traslado calculado según zona del cliente'
    )
    
    formatted_duration = serializers.CharField(source='formatted_duration', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'service_code', 'name', 'description', 'base_price',
            'duration_minutes', 'duration_type', 'duration_value', 'formatted_duration',
            'primary_image', 'provider', 'travel_cost',
            'available', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        if obj.primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.primary_image.url)
            return obj.primary_image.url
        return None


class ServiceDetailSerializer(ServiceListSerializer):
    """Serializer para detalle de servicio"""
    images = serializers.SerializerMethodField()
    
    class Meta(ServiceListSerializer.Meta):
        fields = ServiceListSerializer.Meta.fields + ['images']
    
    def get_images(self, obj):
        request = self.context.get('request')
        images = []
        for img in obj.get_service_images():
            if img:
                if request:
                    images.append(request.build_absolute_uri(img.url))
                else:
                    images.append(img.url)
        return images
