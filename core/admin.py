from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

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
        'created_at'
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
        url = reverse('admin:core_booking_change', args=[obj.booking.id])
        return format_html('<a href="{}">Reserva #{}</a>', url, obj.booking.id)
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
    list_display = ['booking_id', 'customer_name', 'provider_name', 'status_display', 'payment_display', 'scheduled_time', 'total_cost']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['id', 'customer__username', 'provider__username']
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Información de la Reserva', {
            'fields': ('id', 'customer', 'provider', 'status', 'scheduled_time')
        }),
        ('Servicios', {
            'fields': ('service_list', 'location')
        }),
        ('Pago', {
            'fields': ('payment_status', 'total_cost', 'payment_method')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def booking_id(self, obj):
        return f'#{str(obj.id)[:8]}'
    booking_id.short_description = 'ID Reserva'
    
    def customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username
    customer_name.short_description = 'Cliente'
    
    def provider_name(self, obj):
        return obj.provider.get_full_name() or obj.provider.username
    provider_name.short_description = 'Proveedor'
    
    def status_display(self, obj):
        colors = {
            'pending': '#FFC107',
            'accepted': '#17A2B8',
            'completed': '#28A745',
            'cancelled': '#DC3545',
            'dispute': '#E83E8C',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Estado'
    
    def payment_display(self, obj):
        colors = {
            'pending': '#FFC107',
            'pending_validation': '#FF6B6B',
            'paid': '#28A745',
            'refunded': '#6C757D',
        }
        color = colors.get(obj.payment_status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_display.short_description = 'Pago'


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
    list_display = ['name', 'code', 'is_active_display', 'requires_proof', 'requires_reference', 'display_order']
    list_filter = ['is_active', 'requires_proof', 'requires_reference']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'code', 'description', 'icon')
        }),
        ('Configuración', {
            'fields': ('is_active', 'requires_proof', 'requires_reference', 'display_order')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('✅ Activo')
        return format_html('❌ Inactivo')
    is_active_display.short_description = 'Estado'


# ============================================
# ADMIN: BankAccount
# ============================================


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'get_masked_account', 'account_type', 'is_active_display', 'display_order']
    list_filter = ['is_active', 'account_type', 'bank_name']
    search_fields = ['bank_name', 'account_holder', 'account_number']
    ordering = ['display_order', 'bank_name']
    
    fieldsets = (
        ('Información del Banco', {
            'fields': ('bank_name', 'account_type', 'swift_code', 'bank_code')
        }),
        ('Datos de la Cuenta', {
            'fields': ('account_number', 'account_holder', 'id_number')
        }),
        ('Configuración', {
            'fields': ('is_active', 'display_order', 'notes')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_masked_account(self, obj):
        return obj.get_masked_account_number()
    get_masked_account.short_description = 'Número de Cuenta'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('✅ Activa')
        return format_html('❌ Inactiva')
    is_active_display.short_description = 'Estado'


# ============================================
# ADMIN: PaymentProof
# ============================================

@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking_link', 'customer_name', 'reference_code', 
                    'verified_display', 'proof_image_thumbnail', 'created_at', 'approve_button']
    list_filter = ['verified', 'created_at', 'payment_method', 'bank_account']
    search_fields = ['reference_code', 'booking__customer__username', 'booking__id']
    date_hierarchy = 'created_at'
    actions = ['approve_payments', 'reject_payments']
    
    fieldsets = (
        ('Información de la Reserva', {
            'fields': ('booking', 'payment_method', 'bank_account')
        }),
        ('Detalles del Pago', {
            'fields': ('reference_code', 'proof_image', 'proof_image_preview')
        }),
        ('Verificación', {
            'fields': ('verified', 'verified_by', 'verified_at', 'notes')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'proof_image_preview')

    # CAMBIO #4.5: Agregar columna de thumbnail
    def proof_image_thumbnail(self, obj):
        if obj.proof_image:
            return format_html(
                '<a href="{}" target="_blank" title="Ver imagen completa">'
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px; cursor: pointer;" />'
                '</a>',
                obj.proof_image.url,
                obj.proof_image.url
            )
        return '—'
    proof_image_thumbnail.short_description = 'Comprobante'

    # CAMBIO #4.5: Agregar botón de aprobación en la lista
    def approve_button(self, obj):
        if not obj.verified:
            return format_html(
                '<a class="button" href="#" onclick="approvePayment({}, event)">'
                '<i class="fas fa-check"></i> Aprobar'
                '</a>',
                obj.id
            )
        return '✓ Aprobado'
    approve_button.short_description = 'Acción'
    
    def booking_link(self, obj):
        # Simplemente mostrar el ID sin intentar hacer reverse
        # Ya que Booking puede no estar registrado en admin
        return format_html(
            '<strong>#{}</strong>',
            str(obj.booking.id)[:8]
        )
    booking_link.short_description = 'Reserva'
    
    def customer_name(self, obj):
        return obj.booking.customer.get_full_name() or obj.booking.customer.username
    customer_name.short_description = 'Cliente'
    
    def verified_display(self, obj):
        if obj.verified:
            return format_html('✅ Verificado')
        return format_html('⏳ Pendiente')
    verified_display.short_description = 'Estado'
    
    def proof_image_preview(self, obj):
        if obj.proof_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="300" height="auto" style="border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />'
                '</a><br>'
                '<a href="{}" target="_blank" class="button" style="margin-top: 10px; display: inline-block;">'
                '<i class="fas fa-download"></i> Descargar Comprobante'
                '</a>',
                obj.proof_image.url,
                obj.proof_image.url,
                obj.proof_image.url
            )
        return "Sin imagen"
    proof_image_preview.short_description = 'Vista Previa del Comprobante'

    def approve_payments(self, request, queryset):
        """Acción masiva mejorada para aprobar pagos"""
        count = 0
        for proof in queryset.filter(verified=False):
            proof.verified = True
            proof.verified_by = request.user
            proof.verified_at = timezone.now()
            proof.save()
            
            # Actualizar reserva a pagada
            booking = proof.booking
            booking.payment_status = 'paid'
            booking.save()
            
            # Notificaciones (código existente)
            Notification.objects.create(
                user=booking.customer,
                notification_type='payment_verified',
                title='✅ Pago Verificado',
                message=f'Tu pago para la reserva #{booking.id} ha sido verificado y confirmado.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='payment_verified',
                title='✅ Pago Confirmado',
                message=f'El pago de {booking.customer.get_full_name()} ha sido verificado.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            count += 1
        
        self.message_user(request, f'{count} pago(s) aprobado(s) exitosamente.')
    approve_payments.short_description = '✅ Aprobar pago(s) seleccionado(s)'
    
    def reject_payment(self, request, queryset):
        """Acción para rechazar pagos"""
        for proof in queryset.filter(verified=False):
            booking = proof.booking
            
            # Notificar al cliente
            Notification.objects.create(
                user=booking.customer,
                notification_type='payment_received',
                title='❌ Pago Rechazado',
                message=f'Tu comprobante de pago fue rechazado. Por favor verifica los datos e intenta nuevamente.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            # Mantener en estado pendiente para que intente de nuevo
            proof.verified = False
            proof.notes = 'Rechazado - El cliente puede reintentar'
            proof.save()
        
        self.message_user(request, f'{len(queryset)} pago(s) marcado(s) como rechazado(s).')
    reject_payment.short_description = '❌ Rechazar pago(s) seleccionado(s)'


# ============================================
# ADMIN: Notification
# ============================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read_display', 'created_at']
    list_filter = ['is_read', 'notification_type', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'user', 'title', 'message', 'notification_type')
    ordering = ['-created_at']
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Notificación', {
            'fields': ('notification_type', 'title', 'message', 'is_read')
        }),
        ('Relacionados', {
            'fields': ('booking', 'action_url'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read']
    
    def is_read_display(self, obj):
        if obj.is_read:
            return format_html('✅ Leída')
        return format_html('📬 No leída')
    is_read_display.short_description = 'Estado'
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f'{queryset.count()} notificación(es) marcada(s) como leída(s).')
    mark_as_read.short_description = 'Marcar como leída'
    
    def has_add_permission(self, request):
        return False  # No se pueden crear notificaciones desde admin
    
    def has_delete_permission(self, request, obj=None):
        return False  # No se pueden eliminar notificaciones