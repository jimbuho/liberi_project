from rest_framework import serializers
from apps.core.models import (
    ProviderProfile, Service, ProviderLocation,
    ProviderSchedule, ProviderUnavailability, ProviderZoneCost,
    Bank, ProviderBankAccount, WithdrawalRequest, Category, Zone
)
from .services import CategorySerializer
from .bookings import BookingListSerializer, ReviewSerializer


class OnboardingStepSerializer(serializers.Serializer):
    """Paso del checklist de onboarding"""
    id = serializers.IntegerField()
    label = serializers.CharField()
    done = serializers.BooleanField()
    status = serializers.CharField()  # locked, pending, done, rejected, processing
    locked = serializers.BooleanField()
    url = serializers.CharField(allow_null=True, required=False)
    is_processing = serializers.BooleanField(required=False)
    is_rejected = serializers.BooleanField(required=False)


class DashboardStatsSerializer(serializers.Serializer):
    """Estadísticas del dashboard"""
    total_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    active_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    rating_avg = serializers.FloatField()
    total_reviews = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    """Dashboard completo del proveedor"""
    stats = DashboardStatsSerializer()
    upcoming_bookings = BookingListSerializer(many=True)
    recent_reviews = ReviewSerializer(many=True)
    onboarding_progress = serializers.IntegerField()
    onboarding_steps = OnboardingStepSerializer(many=True)


class ProviderProfileDetailSerializer(serializers.ModelSerializer):
    """Perfil detallado del proveedor"""
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False)
    coverage_zones = serializers.SerializerMethodField()
    rejection_reasons_parsed = serializers.SerializerMethodField()
    
    # Campos computados para clarificar requisitos según modalidad
    service_mode_display = serializers.CharField(source='get_service_mode_display', read_only=True)
    requires_coverage = serializers.SerializerMethodField()
    requires_travel_costs = serializers.SerializerMethodField()
    
    class Meta:
        model = ProviderProfile
        fields = [
            'slug', 'business_name', 'description', 'profile_photo',
            'category', 'category_id', 'service_mode', 'service_mode_display',
            'requires_coverage', 'requires_travel_costs',
            'status', 'is_active', 'registration_step', 'documents_verified',
            'coverage_zones', 'rejection_reasons', 'rejection_reasons_parsed',
            'verification_attempts', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'slug', 'status', 'documents_verified', 'registration_step',
            'verification_attempts', 'created_at', 'updated_at'
        ]
    
    def get_coverage_zones(self, obj):
        from .services import ZoneSerializer
        return ZoneSerializer(obj.coverage_zones.all(), many=True).data
    
    def get_rejection_reasons_parsed(self, obj):
        """Parse rejection reasons JSON"""
        if not obj.rejection_reasons:
            return []
        try:
            import json
            return json.loads(obj.rejection_reasons)
        except:
            return [{'code': 'OBSERVACIÓN', 'message': obj.rejection_reasons}]
    
    def get_requires_coverage(self, obj):
        """Indica si esta modalidad requiere configurar zonas de cobertura"""
        return obj.service_mode in ['home', 'both']
    
    def get_requires_travel_costs(self, obj):
        """Indica si esta modalidad requiere configurar costos de traslado"""
        return obj.service_mode in ['home', 'both']


class ProviderServiceSerializer(serializers.ModelSerializer):
    """Serializer para servicios del proveedor"""
    images = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'service_code', 'name', 'description', 'base_price',
            'duration_minutes', 'available', 'images', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'service_code', 'created_at', 'updated_at']
    
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


class ScheduleSerializer(serializers.ModelSerializer):
    """Serializer para horarios del proveedor"""
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = ProviderSchedule
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'is_active']
        read_only_fields = ['id']


class UnavailabilitySerializer(serializers.ModelSerializer):
    """Serializer para períodos de inactividad"""
    
    class Meta:
        model = ProviderUnavailability
        fields = ['id', 'start_date', 'end_date', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProviderLocationDetailSerializer(serializers.ModelSerializer):
    """Serializer para ubicaciones del proveedor"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    
    class Meta:
        model = ProviderLocation
        fields = [
            'id', 'location_type', 'label', 'address', 'reference',
            'city', 'city_name', 'zone', 'zone_name',
            'latitude', 'longitude', 'whatsapp_number',
            'document_proof', 'is_verified', 'created_at'
        ]
        read_only_fields = ['id', 'is_verified', 'created_at']


class ZoneCostSerializer(serializers.ModelSerializer):
    """Serializer para costos por zona"""
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_id = serializers.IntegerField(source='zone.id', read_only=True)
    
    class Meta:
        model = ProviderZoneCost
        fields = ['id', 'zone', 'zone_id', 'zone_name', 'travel_cost']
        read_only_fields = ['id']


class BankSerializer(serializers.ModelSerializer):
    """Serializer para bancos"""
    
    class Meta:
        model = Bank
        fields = ['id', 'name', 'code']


class ProviderBankAccountSerializer(serializers.ModelSerializer):
    """Serializer para cuentas bancarias del proveedor"""
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    
    class Meta:
        model = ProviderBankAccount
        fields = [
            'id', 'bank', 'bank_name', 'account_type',
            'account_number_masked', 'owner_fullname', 'is_primary',
            'created_at'
        ]
        read_only_fields = ['id', 'account_number_masked', 'created_at']


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer para retiros"""
    bank_account = ProviderBankAccountSerializer(source='provider_bank_account', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'requested_amount', 'commission_percent', 'commission_amount',
            'amount_payable', 'status', 'status_display', 'bank_account',
            'description', 'admin_note', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'commission_percent', 'commission_amount', 'amount_payable',
            'status', 'admin_note', 'created_at', 'updated_at'
        ]
