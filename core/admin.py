from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    Profile, Category, ProviderProfile, Service, Location, Booking, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability, SystemConfig, ProviderZoneCost,
    PaymentMethod, BankAccount, PaymentProof, Notification, Payment
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



@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Administración de pagos con funcionalidad para validar transferencias
    """
    list_display = [
        'id',
        'booking_link',
        'customer_name',
        'amount',
        'payment_method',
        'status_badge',
        'created_at',
        'actions_column'
    ]
    
    list_filter = [
        'status',
        'payment_method',
        'created_at',
        'transfer_date',
    ]
    
    search_fields = [
        'booking__id',
        'booking__customer__username',
        'booking__customer__email',
        'transaction_id',
        'reference_number',
    ]
    
    readonly_fields = [
        'booking',
        'created_at',
        'updated_at',
        'validated_by',
        'validated_at',
        'receipt_preview',
    ]
    
    fieldsets = (
        ('Información General', {
            'fields': (
                'booking',
                'amount',
                'payment_method',
                'status',
            )
        }),
        ('Detalles de Transacción', {
            'fields': (
                'transaction_id',
                'reference_number',
                'transfer_date',
                'transfer_receipt',
                'receipt_preview',
            )
        }),
        ('Validación', {
            'fields': (
                'validated_by',
                'validated_at',
                'notes',
            )
        }),
        ('Metadatos', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_payments', 'reject_payments']
    
    def booking_link(self, obj):
        """Link a la reserva asociada"""
        url = reverse('admin:bookings_booking_change', args=[obj.booking.id])
        return format_html('<a href="{}"">Reserva #{}</a>', url, obj.booking.id)
    booking_link.short_description = 'Reserva'
    
    def customer_name(self, obj):
        """Nombre del cliente"""
        customer = obj.booking.customer
        return customer.get_full_name() or customer.username
    customer_name.short_description = 'Cliente'
    
    def status_badge(self, obj):
        """Badge visual para el estado"""
        colors = {
            'pending': 'orange',
            'pending_validation': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'purple',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def actions_column(self, obj):
        """Columna de acciones rápidas"""
        if obj.status == 'pending_validation':
            approve_url = reverse('admin:approve_payment', args=[obj.id])
            reject_url = reverse('admin:reject_payment', args=[obj.id])
            return format_html(
                '<a class="button" href="{}" style="background-color: #28a745; color: white; '
                'padding: 5px 10px; border-radius: 3px; text-decoration: none; margin-right: 5px;">'
                'Aprobar</a>'
                '<a class="button" href="{}" style="background-color: #dc3545; color: white; '
                'padding: 5px 10px; border-radius: 3px; text-decoration: none;">Rechazar</a>',
                approve_url,
                reject_url
            )
        return '-'
    actions_column.short_description = 'Acciones'
    
    def receipt_preview(self, obj):
        """Preview del comprobante de pago"""
        if obj.transfer_receipt:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />'
                '</a><br><a href="{}" target="_blank" class="button">Descargar Comprobante</a>',
                obj.transfer_receipt.url,
                obj.transfer_receipt.url,
                obj.transfer_receipt.url
            )
        return 'Sin comprobante'
    receipt_preview.short_description = 'Comprobante'
    
    def approve_payments(self, request, queryset):
        """Acción masiva para aprobar pagos"""
        count = 0
        for payment in queryset.filter(status='pending_validation'):
            payment.mark_as_completed(validated_by=request.user)
            count += 1
        
        self.message_user(
            request,
            f'{count} pago(s) aprobado(s) exitosamente.'
        )
    approve_payments.short_description = 'Aprobar pagos seleccionados'
    
    def reject_payments(self, request, queryset):
        """Acción masiva para rechazar pagos"""
        count = queryset.filter(status='pending_validation').update(
            status='failed',
            validated_by=request.user,
            notes='Rechazado desde el admin'
        )
        self.message_user(
            request,
            f'{count} pago(s) rechazado(s).'
        )
    reject_payments.short_description = 'Rechazar pagos seleccionados'
    
    def has_delete_permission(self, request, obj=None):
        """Prevenir eliminación accidental de pagos"""
        return request.user.is_superuser
    
    def get_queryset(self, request):
        """Optimizar consultas"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'booking',
            'booking__customer',
            'validated_by'
        )


# Inline para mostrar pagos en la vista de Booking
class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = [
        'amount',
        'payment_method',
        'status',
        'transaction_id',
        'reference_number',
        'created_at'
    ]
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


# Actualizar BookingAdmin para incluir el inline de pagos
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'customer',
        'provider',
        'status',
        'payment_status_badge',
        'total_cost',
        'scheduled_time',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'payment_status',
        'created_at',
        'scheduled_time'
    ]
    
    search_fields = [
        'customer__username',
        'customer__email',
        'provider__username',
        'id'
    ]
    
    inlines = [PaymentInline]
    
    def payment_status_badge(self, obj):
        """Badge para el estado del pago"""
        colors = {
            'pending': 'orange',
            'pending_validation': 'blue',
            'paid': 'green',
            'refunded': 'purple',
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Estado de Pago'


# Configuración adicional para notificaciones en el admin
class PendingPaymentsFilter(admin.SimpleListFilter):
    """
    Filtro personalizado para mostrar pagos pendientes de validación
    """
    title = 'Validación Pendiente'
    parameter_name = 'needs_validation'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Requiere Validación'),
            ('no', 'Ya Validado'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(status='pending_validation')
        if self.value() == 'no':
            return queryset.exclude(status='pending_validation')

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


# ============================================
# ADMIN: PaymentMethod
# ============================================

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'is_active_badge', 'requires_proof', 
        'requires_reference', 'display_order', 'updated_at'
    ]
    list_filter = ['is_active', 'requires_proof', 'requires_reference']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    list_editable = ['display_order']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'code', 'description', 'icon')
        }),
        ('Configuración', {
            'fields': ('is_active', 'requires_proof', 'requires_reference', 'display_order')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #10B981; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">Activo</span>'
            )
        return format_html(
            '<span style="background-color: #EF4444; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">Inactivo</span>'
        )
    is_active_badge.short_description = 'Estado'
    
    actions = ['activate_methods', 'deactivate_methods']
    
    def activate_methods(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} método(s) de pago activado(s).')
    activate_methods.short_description = 'Activar métodos seleccionados'
    
    def deactivate_methods(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} método(s) de pago desactivado(s).')
    deactivate_methods.short_description = 'Desactivar métodos seleccionados'


# ============================================
# ADMIN: BankAccount
# ============================================


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """
    Administración de cuentas bancarias
    """
    list_display = [
        'bank_name',
        'account_type_display',
        'masked_account_number',
        'account_holder',
        'is_active_badge',
        'display_order',
    ]
    
    list_filter = [
        'is_active',
        'account_type',
        'bank_name',
    ]
    
    search_fields = [
        'bank_name',
        'account_number',
        'account_holder',
        'id_number',
    ]
    
    list_editable = ['display_order']
    
    fieldsets = (
        ('Información del Banco', {
            'fields': (
                'bank_name',
                'bank_code',
                'swift_code',
            )
        }),
        ('Información de la Cuenta', {
            'fields': (
                'account_type',
                'account_number',
                'account_holder',
                'id_number',
            )
        }),
        ('Configuración', {
            'fields': (
                'is_active',
                'display_order',
                'notes',
            )
        }),
        ('Metadatos', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def account_type_display(self, obj):
        """Tipo de cuenta formateado"""
        return obj.get_account_type_display()
    account_type_display.short_description = 'Tipo de Cuenta'
    
    def masked_account_number(self, obj):
        """Número de cuenta parcialmente oculto por seguridad"""
        return obj.get_masked_account_number()
    masked_account_number.short_description = 'Número de Cuenta'
    
    def is_active_badge(self, obj):
        """Badge visual para el estado activo"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">Activa</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">Inactiva</span>'
            )
    is_active_badge.short_description = 'Estado'
    
    actions = ['activate_accounts', 'deactivate_accounts']
    
    def activate_accounts(self, request, queryset):
        """Acción para activar cuentas seleccionadas"""
        count = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{count} cuenta(s) bancaria(s) activada(s).'
        )
    activate_accounts.short_description = 'Activar cuentas seleccionadas'
    
    def deactivate_accounts(self, request, queryset):
        """Acción para desactivar cuentas seleccionadas"""
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{count} cuenta(s) bancaria(s) desactivada(s).'
        )
    deactivate_accounts.short_description = 'Desactivar cuentas seleccionadas'
    
    def get_queryset(self, request):
        """Optimizar consultas"""
        qs = super().get_queryset(request)
        return qs.order_by('display_order', 'bank_name')


# ============================================
# ADMIN: PaymentProof
# ============================================

@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = [
        'booking_link', 'payment_method', 'bank_account', 
        'reference_code', 'verified_badge', 'proof_thumbnail', 
        'created_at'
    ]
    list_filter = ['verified', 'payment_method', 'created_at']  # CAMBIADO: is_verified → verified
    search_fields = ['booking__id', 'reference_code', 'booking__customer__username']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información de Pago', {
            'fields': ('booking', 'payment_method', 'bank_account', 'reference_code')
        }),
        ('Comprobante', {
            'fields': ('proof_image', 'proof_image_preview')
        }),
        ('Verificación', {
            'fields': ('verified', 'verified_by', 'verified_at', 'notes')  # CAMBIADO: is_verified → verified
        }),
        ('Fechas', {
            'fields': ('created_at',),  # CAMBIADO: removido updated_at
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'verified_by', 'verified_at', 'proof_image_preview']  # CAMBIADO: removido updated_at
    
    def booking_link(self, obj):
        url = reverse('admin:core_booking_change', args=[obj.booking.id])
        return format_html('<a href="{}">{}</a>', url, f'Reserva #{obj.booking.id}')
    booking_link.short_description = 'Reserva'
    
    def verified_badge(self, obj):  # CAMBIADO nombre de is_verified_badge a verified_badge
        if obj.verified:  # CAMBIADO: is_verified → verified
            return format_html(
                '<span style="background-color: #10B981; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">✓ Verificado</span>'
            )
        return format_html(
            '<span style="background-color: #F59E0B; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">⏳ Pendiente</span>'
        )
    verified_badge.short_description = 'Estado'
    
    def proof_thumbnail(self, obj):
        if obj.proof_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />'
                '</a>',
                obj.proof_image.url,
                obj.proof_image.url
            )
        return '-'
    proof_thumbnail.short_description = 'Comprobante'
    
    def proof_image_preview(self, obj):
        if obj.proof_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 600px; max-height: 400px; border-radius: 8px;" />'
                '</a>',
                obj.proof_image.url,
                obj.proof_image.url
            )
        return 'No hay imagen'
    proof_image_preview.short_description = 'Vista Previa del Comprobante'
    
    actions = ['verify_payments']
    
    def verify_payments(self, request, queryset):
        """Verificar pagos y actualizar estado de reserva"""
        from django.utils import timezone
        
        updated = 0
        for proof in queryset.filter(verified=False):
            # Marcar como verificado
            proof.verified = True
            proof.verified_by = request.user
            proof.verified_at = timezone.now()
            proof.save()
            
            # Actualizar estado de la reserva
            proof.booking.payment_status = 'paid'
            proof.booking.save()
            
            # Crear notificación para el cliente
            Notification.objects.create(
                user=proof.booking.customer,
                notification_type='payment_verified',
                title='Pago Verificado',
                message=f'Tu pago para la reserva #{str(proof.booking.id)[:8]} ha sido verificado. ¡Todo listo!',
                booking=proof.booking,
                action_url=f'/bookings/{proof.booking.id}/'
            )
            
            # Notificar al proveedor
            Notification.objects.create(
                user=proof.booking.provider,
                notification_type='payment_verified',
                title='Pago Verificado',
                message=f'El pago de {proof.booking.customer.get_full_name()} para la reserva #{str(proof.booking.id)[:8]} ha sido verificado.',
                booking=proof.booking,
                action_url=f'/bookings/{proof.booking.id}/'
            )
            
        updated += 1
        
        self.message_user(request, f'{updated} pago(s) verificado(s) exitosamente.')
    verify_payments.short_description = 'Verificar y confirmar pagos seleccionados'


# ============================================
# ADMIN: Notification
# ============================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'notification_type', 'title_truncated', 
        'is_read_badge', 'booking_link', 'created_at'
    ]
    list_filter = ['is_read', 'notification_type', 'created_at']
    search_fields = ['user__username', 'user__email', 'title', 'message']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Destinatario', {
            'fields': ('user',)
        }),
        ('Contenido', {
            'fields': ('notification_type', 'title', 'message', 'action_url')
        }),
        ('Relaciones', {
            'fields': ('booking',)
        }),
        ('Estado', {
            'fields': ('is_read',)
        }),
        ('Fechas', {
            'fields': ('created_at',),  # CAMBIADO: removido updated_at
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']  # CAMBIADO: removido updated_at
    
    def title_truncated(self, obj):
        if len(obj.title) > 50:
            return obj.title[:50] + '...'
        return obj.title
    title_truncated.short_description = 'Título'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="background-color: #6B7280; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">Leída</span>'
            )
        return format_html(
            '<span style="background-color: #3FB8C4; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">No leída</span>'
        )
    is_read_badge.short_description = 'Estado'
    
    def booking_link(self, obj):
        if obj.booking:
            url = reverse('admin:core_booking_change', args=[obj.booking.id])
            return format_html('<a href="{}">{}</a>', url, f'Reserva #{obj.booking.id}')
        return '-'
    booking_link.short_description = 'Reserva'
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notificación(es) marcada(s) como leída(s).')
    mark_as_read.short_description = 'Marcar como leídas'
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notificación(es) marcada(s) como no leída(s).')
    mark_as_unread.short_description = 'Marcar como no leídas'