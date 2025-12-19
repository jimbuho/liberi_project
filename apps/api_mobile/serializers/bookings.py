from rest_framework import serializers
from apps.core.models import (
    Booking, Service, Location, Review,
    ProviderLocation
)
from django.contrib.auth.models import User


class BookingServiceInfoSerializer(serializers.Serializer):
    """Info básica del servicio en la reserva"""
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=8, decimal_places=2)


class BookingListSerializer(serializers.ModelSerializer):
    """Serializer para listado de reservas"""
    service_names = serializers.SerializerMethodField()
    provider_name = serializers.CharField(source='provider.provider_profile.get_display_name', read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'slug', 'service_names', 'provider_name', 'customer_name',
            'scheduled_time', 'total_cost', 'status', 'status_display',
            'payment_status', 'created_at'
        ]
    
    def get_service_names(self, obj):
        return obj.get_services_display()


class LocationSerializer(serializers.ModelSerializer):
    """Serializer para ubicación del cliente"""
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = Location
        fields = [
            'id', 'address', 'reference', 'label', 'recipient_name',
            'zone', 'zone_name', 'city', 'city_name',
            'latitude', 'longitude'
        ]


class ProviderLocationSerializer(serializers.ModelSerializer):
    """Serializer para ubicación del proveedor"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    
    class Meta:
        model = ProviderLocation
        fields = [
            'id', 'location_type', 'label', 'address', 'reference',
            'city', 'city_name', 'zone', 'zone_name',
            'latitude', 'longitude', 'whatsapp_number', 'is_verified'
        ]


class ContactInfoSerializer(serializers.Serializer):
    """Info de contacto (cuando está permitido)"""
    name = serializers.CharField()
    phone = serializers.CharField()


class BookingDetailSerializer(BookingListSerializer):
    """Serializer para detalle de reserva"""
    location = LocationSerializer(read_only=True)
    provider_location = ProviderLocationSerializer(read_only=True)
    can_contact = serializers.SerializerMethodField()
    contact_info = serializers.SerializerMethodField()
    completion_code = serializers.SerializerMethodField()
    
    class Meta(BookingListSerializer.Meta):
        fields = BookingListSerializer.Meta.fields + [
            'sub_total_cost', 'travel_cost', 'tax', 'service',
            'notes', 'location', 'provider_location',
            'can_contact', 'contact_info', 'completion_code',
            'provider_completed_at', 'customer_completed_at'
        ]
    
    def get_can_contact(self, obj):
        """Determina si se puede mostrar info de contacto"""
        request = self.context.get('request')
        if not request:
            return False
        
        # Solo si está pagado y faltan 2 horas o menos
        if obj.payment_status != 'paid' or obj.status != 'accepted':
            return False
        
        return obj.hours_until <= 2
    
    def get_contact_info(self, obj):
        """Retorna info de contacto si está permitido"""
        if not self.get_can_contact(obj):
            return None
        
        request = self.context.get('request')
        if request.user == obj.customer:
            # Cliente ve info del proveedor
            return {
                'name': obj.provider.get_full_name(),
                'phone': obj.provider.profile.phone if hasattr(obj.provider, 'profile') else None,
            }
        else:
            # Proveedor ve info del cliente
            return {
                'name': obj.customer.get_full_name(),
                'phone': obj.customer.profile.phone if hasattr(obj.customer, 'profile') else None,
            }
    
    def get_completion_code(self, obj):
        """Retorna código de completación si el usuario es cliente y corresponde"""
        request = self.context.get('request')
        if request and request.user == obj.customer:
            if obj.should_show_completion_code():
                if not obj.completion_code:
                    obj.generate_completion_code()
                return obj.completion_code
        return None


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer para reseñas"""
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'rating', 'comment', 'customer_name', 'created_at']
        read_only_fields = ['id', 'customer_name', 'created_at']
