from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import (
    Profile, Category, ProviderProfile, Service, Location, Booking, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability, SystemConfig, ProviderZoneCost
)

# Inline para Profile en User admin
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Perfil'
    fields = ['phone', 'role', 'verified']


# Extender UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ['username', 'email', 'get_role', 'get_verified', 'get_phone', 'date_joined']
    list_filter = ['profile__role', 'profile__verified', 'is_active']
    
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return '-'
    get_role.short_description = 'Rol'
    
    def get_verified(self, obj):
        if hasattr(obj, 'profile'):
            return '✓' if obj.profile.verified else '✗'
        return '-'
    get_verified.short_description = 'Verificado'
    
    def get_phone(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.phone
        return '-'
    get_phone.short_description = 'Teléfono'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'verified', 'phone', 'created_at']
    list_filter = ['role', 'verified']
    search_fields = ['user__username', 'user__email', 'phone']
    actions = ['verify_profiles']
    
    def verify_profiles(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f'{updated} perfil(es) verificado(s).')
    verify_profiles.short_description = 'Verificar perfiles seleccionados'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'created_at', 'service_count']
    search_fields = ['name']
    
    def service_count(self, obj):
        count = Service.objects.filter(
            provider__provider_profile__category=obj,
            available=True
        ).count()
        return count
    service_count.short_description = 'Servicios activos'


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'status', 'is_active', 'avg_travel_cost', 'rating', 'created_at']
    list_filter = ['status', 'is_active', 'category', 'created_at']
    search_fields = ['user__username', 'user__email', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['coverage_zones']
    actions = ['approve_providers', 'reject_providers', 'activate_providers', 'deactivate_providers']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('user', 'category', 'description')
        }),
        ('Cobertura y Costos', {
            'fields': ('coverage_zones', 'avg_travel_cost')
        }),
        ('Estado', {
            'fields': ('status', 'is_active')
        }),
        ('Documentos', {
            'fields': ('signed_contract_url', 'id_card_front', 'id_card_back'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def rating(self, obj):
        from django.db.models import Avg
        avg = Review.objects.filter(booking__provider=obj.user).aggregate(Avg('rating'))
        rating = avg['rating__avg'] or 0
        stars = '⭐' * int(rating)
        return f'{stars} ({rating:.1f})'
    rating.short_description = 'Calificación'
    
    def approve_providers(self, request, queryset):
        updated = queryset.update(status='approved')
        self.message_user(request, f'{updated} proveedor(es) aprobado(s).')
    approve_providers.short_description = 'Aprobar proveedores'
    
    def reject_providers(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'{updated} proveedor(es) rechazado(s).')
    reject_providers.short_description = 'Rechazar proveedores'
    
    def activate_providers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} proveedor(es) activado(s).')
    activate_providers.short_description = 'Activar proveedores'
    
    def deactivate_providers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} proveedor(es) desactivado(s).')
    deactivate_providers.short_description = 'Desactivar proveedores'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'category_name', 'base_price', 'duration_minutes', 'available', 'created_at']
    list_filter = ['available', 'created_at', 'provider__provider_profile__category']
    search_fields = ['name', 'description', 'provider__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def category_name(self, obj):
        if hasattr(obj.provider, 'provider_profile'):
            return obj.provider.provider_profile.category.name
        return '-'
    category_name.short_description = 'Categoría'


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'active', 'provider_count', 'created_at']
    list_filter = ['active', 'city']
    search_fields = ['name', 'city']
    actions = ['activate_zones', 'deactivate_zones']
    
    def provider_count(self, obj):
        return obj.providers.count()
    provider_count.short_description = 'Proveedores'
    
    def activate_zones(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} zona(s) activada(s).')
    activate_zones.short_description = 'Activar zonas'
    
    def deactivate_zones(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} zona(s) desactivada(s).')
    deactivate_zones.short_description = 'Desactivar zonas'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'label', 'zone', 'address_short', 'created_at']
    list_filter = ['label', 'zone']
    search_fields = ['customer__username', 'address', 'zone__name']
    readonly_fields = ['created_at']
    
    def address_short(self, obj):
        return obj.address[:50] + '...' if len(obj.address) > 50 else obj.address
    address_short.short_description = 'Dirección'


@admin.register(ProviderSchedule)
class ProviderScheduleAdmin(admin.ModelAdmin):
    list_display = ['provider', 'day_name', 'start_time', 'end_time', 'is_active']
    list_filter = ['day_of_week', 'is_active', 'provider__provider_profile__category']
    search_fields = ['provider__username']
    
    def day_name(self, obj):
        return obj.get_day_of_week_display()
    day_name.short_description = 'Día'


@admin.register(ProviderUnavailability)
class ProviderUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ['provider', 'start_date', 'end_date', 'reason', 'duration_days', 'created_at']
    list_filter = ['start_date', 'provider__provider_profile__category']
    search_fields = ['provider__username', 'reason']
    date_hierarchy = 'start_date'
    
    def duration_days(self, obj):
        delta = obj.end_date - obj.start_date
        return delta.days + 1
    duration_days.short_description = 'Días'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['booking_id', 'customer', 'provider', 'status', 'payment_status', 'total_cost', 'scheduled_time']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['customer__username', 'provider__username', 'id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'scheduled_time'
    
    fieldsets = (
        ('Información de la Reserva', {
            'fields': ('id', 'customer', 'provider', 'service_list', 'total_cost')
        }),
        ('Ubicación y Tiempo', {
            'fields': ('location', 'scheduled_time')
        }),
        ('Estado', {
            'fields': ('status', 'payment_status', 'payment_method')
        }),
        ('Notas', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def booking_id(self, obj):
        return str(obj.id)[:8]
    booking_id.short_description = 'ID'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['booking_id', 'customer', 'provider_name', 'rating', 'has_comment', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['customer__username', 'booking__provider__username', 'comment']
    readonly_fields = ['created_at']
    
    def booking_id(self, obj):
        return str(obj.booking.id)[:8]
    booking_id.short_description = 'Reserva'
    
    def provider_name(self, obj):
        return obj.booking.provider.get_full_name()
    provider_name.short_description = 'Proveedor'
    
    def has_comment(self, obj):
        return '✓' if obj.comment else '✗'
    has_comment.short_description = 'Comentario'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp', 'ip_address']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'action']
    readonly_fields = ['user', 'action', 'timestamp', 'metadata', 'ip_address']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'value_type', 'description_short', 'updated_at', 'updated_by']
    list_filter = ['value_type', 'updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at', 'updated_by']
    
    fieldsets = (
        ('Información', {
            'fields': ('key', 'value', 'value_type')
        }),
        ('Descripción', {
            'fields': ('description',)
        }),
        ('Auditoría', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Descripción'
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar configuraciones críticas
        if obj and obj.key in ['max_travel_cost', 'min_booking_hours']:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ProviderZoneCost)
class ProviderZoneCostAdmin(admin.ModelAdmin):
    list_display = ['provider', 'zone', 'travel_cost', 'updated_at']
    list_filter = ['zone', 'provider__provider_profile__category']
    search_fields = ['provider__username', 'provider__first_name', 'provider__last_name', 'zone__name']
    autocomplete_fields = ['provider', 'zone']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Información', {
            'fields': ('provider', 'zone', 'travel_cost')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('provider', 'zone')