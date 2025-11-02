from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Profile, Category, ProviderProfile, Service, Location, Booking, Review,
    Zone, ProviderSchedule, ProviderUnavailability, ProviderZoneCost, SystemConfig
)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['phone', 'role', 'verified', 'created_at']
        read_only_fields = ['verified', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, 
                                    style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, min_length=8,
                                            style={'input_type': 'password'})
    phone = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=Profile.ROLE_CHOICES, default='customer')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 
                 'phone', 'role', 'first_name', 'last_name']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return data
    
    def create(self, validated_data):
        # Extraer datos del profile
        phone = validated_data.pop('phone')
        role = validated_data.pop('role')
        validated_data.pop('password_confirm')
        
        # Crear usuario
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Crear profile
        Profile.objects.create(
            user=user,
            phone=phone,
            role=role
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Credenciales inválidas")


class CategorySerializer(serializers.ModelSerializer):
    service_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    def get_service_count(self, obj):
        return Service.objects.filter(
            provider__provider_profile__category=obj,
            available=True
        ).count()


class ServiceSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.get_full_name', read_only=True)
    provider_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['provider', 'created_at', 'updated_at']
    
    def get_provider_rating(self, obj):
        from django.db.models import Avg
        result = Review.objects.filter(
            booking__provider=obj.provider
        ).aggregate(Avg('rating'))
        return round(result['rating__avg'] or 0, 1)


class ZoneSerializer(serializers.ModelSerializer):
    """Serializer para zonas"""
    class Meta:
        model = Zone
        fields = ['id', 'name', 'description', 'city', 'active']


class ProviderScheduleSerializer(serializers.ModelSerializer):
    """Serializer para horarios del proveedor"""
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = ProviderSchedule
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'is_active']


class ProviderUnavailabilitySerializer(serializers.ModelSerializer):
    """Serializer para días de inactividad"""
    class Meta:
        model = ProviderUnavailability
        fields = ['id', 'start_date', 'end_date', 'reason', 'created_at']
        read_only_fields = ['created_at']
    
    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("La fecha de fin debe ser mayor o igual a la fecha de inicio")
        return data

class LocationSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    
    class Meta:
        model = Location
        fields = '__all__'
        read_only_fields = ['customer', 'created_at']
    
    def validate(self, data):
        # Validar que las coordenadas estén presentes
        if not data.get('latitude') or not data.get('longitude'):
            raise serializers.ValidationError("Las coordenadas son requeridas")
        return data

class BookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    provider_name = serializers.CharField(source='provider.get_full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.profile.phone', read_only=True)
    provider_phone = serializers.CharField(source='provider.profile.phone', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)
    can_review = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()
    can_contact = serializers.SerializerMethodField()
    contact_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['customer', 'payment_status', 'created_at', 'updated_at']
    
    def validate_scheduled_time(self, value):
        """Validar que la fecha sea al menos 1 hora en el futuro"""
        now = timezone.now()
        min_time = now + timedelta(hours=1)
        
        if value < min_time:
            raise serializers.ValidationError(
                f"La reserva debe ser al menos 1 hora en el futuro. "
                f"Hora mínima: {min_time.strftime('%Y-%m-%d %H:%M')}"
            )
        
        return value
    
    def get_can_review(self, obj):
        return obj.status == 'completed' and not hasattr(obj, 'review')
    
    def get_can_complete(self, obj):
        """Determinar si una reserva puede ser completada"""
        # Debe estar aceptada
        if obj.status != 'accepted':
            return False
        
        # Debe estar pagada
        if obj.payment_status != 'paid':
            return False
        
        # La fecha/hora programada debe haber pasado o estar cerca (30 min antes)
        now = timezone.now()
        scheduled = obj.scheduled_time
        time_diff = (now - scheduled).total_seconds() / 60  # diferencia en minutos
        
        # Permitir completar 30 minutos antes de la hora programada
        if time_diff >= -30:
            return True
        
        return False

    def get_can_contact(self, obj):
        """Determina si el usuario puede ver datos de contacto"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        now = timezone.now()
        time_until_booking = obj.scheduled_time - now
        hours_until = time_until_booking.total_seconds() / 3600
        
        if user == obj.customer:
            # Cliente: debe haber pagado y faltar 2 horas o menos
            return obj.payment_status == 'paid' and hours_until <= 2
        elif user == obj.provider:
            # Proveedor: solo faltar 2 horas o menos
            return hours_until <= 2
        
        return False
    
    def get_contact_message(self, obj):
        """Mensaje explicativo si no puede contactar"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        user = request.user
        now = timezone.now()
        time_until_booking = obj.scheduled_time - now
        hours_until = time_until_booking.total_seconds() / 3600
        
        if user == obj.customer:
            if obj.payment_status != 'paid':
                return 'Completa el pago para acceder a los datos de contacto'
            elif hours_until > 2:
                hours_remaining = int(hours_until)
                return f'El contacto estará disponible 2 horas antes de tu cita (faltan {hours_remaining} horas)'
        elif user == obj.provider:
            if hours_until > 2:
                hours_remaining = int(hours_until)
                return f'El contacto estará disponible 2 horas antes de la cita (faltan {hours_remaining} horas)'
        
        return None

class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    provider_name = serializers.CharField(source='booking.provider.get_full_name', read_only=True)
    
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['customer', 'created_at']
    
    def validate_booking(self, value):
        if value.status != 'completed':
            raise serializers.ValidationError("Solo se pueden reseñar reservas completadas")
        if hasattr(value, 'review'):
            raise serializers.ValidationError("Esta reserva ya tiene una reseña")
        return value

class ProviderZoneCostSerializer(serializers.ModelSerializer):
    """Serializer para costos por zona del proveedor"""
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_city = serializers.CharField(source='zone.city', read_only=True)
    
    class Meta:
        model = ProviderZoneCost
        fields = ['id', 'zone', 'zone_name', 'zone_city', 'travel_cost', 'created_at']
        read_only_fields = ['created_at']
    
    def validate_travel_cost(self, value):
        """Validar que no exceda el máximo"""
        max_cost = SystemConfig.get_config('max_travel_cost', 5)
        if value > max_cost:
            raise serializers.ValidationError(
                f'El costo de traslado no puede superar ${max_cost} USD'
            )
        return value
    
class ProviderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    coverage_zones_data = ZoneSerializer(source='coverage_zones', many=True, read_only=True)
    coverage_zone_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Zone.objects.filter(active=True),
        source='coverage_zones',
        write_only=True
    )
    zone_costs = ProviderZoneCostSerializer(source='user.zone_costs', many=True, read_only=True)
    rating_avg = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    schedules = ProviderScheduleSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProviderProfile
        fields = '__all__'
        read_only_fields = ['user', 'status', 'created_at', 'updated_at']
    
    def get_rating_avg(self, obj):
        from django.db.models import Avg
        result = Review.objects.filter(
            booking__provider=obj.user
        ).aggregate(Avg('rating'))
        return round(result['rating__avg'] or 0, 1)
    
    def get_total_reviews(self, obj):
        return Review.objects.filter(booking__provider=obj.user).count()

class SystemConfigSerializer(serializers.ModelSerializer):
    """Serializer para configuraciones del sistema"""
    typed_value = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemConfig
        fields = ['id', 'key', 'value', 'typed_value', 'description', 'value_type', 'updated_at']
        read_only_fields = ['updated_at']
    
    def get_typed_value(self, obj):
        return obj.get_value()
