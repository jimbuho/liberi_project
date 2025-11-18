from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

import requests
import json
import logging

from .models import (
    Profile, Category, ProviderProfile, Service, Location, Booking, Review, AuditLog,
    Zone, ProviderSchedule, ProviderUnavailability, SystemConfig, ProviderZoneCost,
    PaymentMethod, BankAccount, PaymentProof, Notification, Payment,
    WithdrawalRequest, ProviderBankAccount, Bank, City
)

logger = logging.getLogger(__name__)

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


# ============================================
# ADMIN: City
# ============================================

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'country', 'active_display', 'zones_count', 'display_order', 'created_at']
    list_filter = ['active', 'country', 'created_at']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'zones_list']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'code', 'country')
        }),
        ('Configuración', {
            'fields': ('active', 'display_order')
        }),
        ('Zonas', {
            'fields': ('zones_list',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_cities', 'deactivate_cities']
    
    def active_display(self, obj):
        """Mostrar estado de la ciudad con icono"""
        if obj.active:
            return format_html('✅ Activa')
        return format_html('❌ Inactiva')
    active_display.short_description = 'Estado'
    
    def zones_count(self, obj):
        """Contar zonas asociadas a la ciudad"""
        count = obj.zones.count()
        return format_html(
            '<strong>{}</strong> zona{}'.format(
                count,
                's' if count != 1 else ''
            )
        )
    zones_count.short_description = 'Zonas'
    
    def zones_list(self, obj):
        """Listar todas las zonas de la ciudad"""
        zones = obj.zones.all()
        if not zones:
            return 'No hay zonas registradas'
        
        zone_list = '<ul style="margin: 5px 0;">'
        for zone in zones:
            zone_list += f'<li>{zone.name}</li>'
        zone_list += '</ul>'
        
        return format_html(zone_list)
    zones_list.short_description = 'Zonas Registradas'
    
    def activate_cities(self, request, queryset):
        """Activar ciudades seleccionadas"""
        updated = queryset.update(active=True)
        self.message_user(
            request,
            f'✅ {updated} ciudad(es) activada(s).',
            messages.SUCCESS
        )
    activate_cities.short_description = '✅ Activar ciudades seleccionadas'
    
    def deactivate_cities(self, request, queryset):
        """Desactivar ciudades seleccionadas"""
        updated = queryset.update(active=False)
        self.message_user(
            request,
            f'❌ {updated} ciudad(es) desactivada(s).',
            messages.WARNING
        )
    deactivate_cities.short_description = '❌ Desactivar ciudades seleccionadas'


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 
        'category', 
        'contact_info',
        'documents_preview',
        'coverage_info',
        'status_badge', 
        'quick_actions',
        'created_at'
    ]
    list_filter = ['status', 'is_active', 'category', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['coverage_zones']
    
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
    
    class Media:
        css = {
            'all': ('admin/css/provider_review.css',)
        }
        js = ('admin/js/provider_review.js',)
    
    def contact_info(self, obj):
        """Información de contacto del proveedor"""
        user = obj.user
        phone = user.profile.phone if hasattr(user, 'profile') else 'N/A'
        return format_html(
            '<strong>{}</strong><br>'
            '<small>📧 {}</small><br>'
            '<small>📱 {}</small>',
            user.get_full_name() or user.username,
            user.email,
            phone
        )
    contact_info.short_description = 'Contacto'
    
    def documents_preview(self, obj):
        """Vista previa de documentos con imágenes thumbnail"""
        docs_html = []
        
        # Contrato firmado
        if obj.signed_contract_url:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                f'<a href="{obj.signed_contract_url}" target="_blank" title="Ver contrato">'
                f'<img src="{obj.signed_contract_url}" style="width: 40px; height: 40px; object-fit: cover; border: 2px solid #28a745; border-radius: 4px; cursor: pointer;">'
                '</a>'
                '<br><small style="font-size: 9px;">📄 Contrato</small>'
                '</div>'
            )
        else:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                '<div style="width: 40px; height: 40px; background: #ddd; border-radius: 4px; display: flex; align-items: center; justify-content: center;">❌</div>'
                '<br><small style="font-size: 9px;">Contrato</small>'
                '</div>'
            )
        
        # Cédula frontal
        if obj.id_card_front:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                f'<a href="{obj.id_card_front.url}" target="_blank" title="Ver cédula frontal">'
                f'<img src="{obj.id_card_front.url}" style="width: 40px; height: 40px; object-fit: cover; border: 2px solid #007bff; border-radius: 4px; cursor: pointer;">'
                '</a>'
                '<br><small style="font-size: 9px;">🪪 Frente</small>'
                '</div>'
            )
        else:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                '<div style="width: 40px; height: 40px; background: #ddd; border-radius: 4px; display: flex; align-items: center; justify-content: center;">❌</div>'
                '<br><small style="font-size: 9px;">Frente</small>'
                '</div>'
            )
        
        # Cédula posterior
        if obj.id_card_back:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                f'<a href="{obj.id_card_back.url}" target="_blank" title="Ver cédula posterior">'
                f'<img src="{obj.id_card_back.url}" style="width: 40px; height: 40px; object-fit: cover; border: 2px solid #007bff; border-radius: 4px; cursor: pointer;">'
                '</a>'
                '<br><small style="font-size: 9px;">🪪 Reverso</small>'
                '</div>'
            )
        else:
            docs_html.append(
                '<div style="display: inline-block; margin: 2px;">'
                '<div style="width: 40px; height: 40px; background: #ddd; border-radius: 4px; display: flex; align-items: center; justify-content: center;">❌</div>'
                '<br><small style="font-size: 9px;">Reverso</small>'
                '</div>'
            )
        
        # Botón de vista detallada - usar format_html para el onclick
        detail_button = format_html(
            '<br><a href="#" class="button" onclick="showProviderDetail({}); return false;" '
            'style="font-size: 11px; padding: 3px 8px; margin-top: 5px;">🔍 Ver Todo</a>',
            obj.pk
        )
        
        return format_html('{}{}', mark_safe(''.join(docs_html)), detail_button)
    documents_preview.short_description = 'Documentos'
    
    def coverage_info(self, obj):
        """Información de cobertura y costos"""
        zones_count = obj.coverage_zones.count()
        services = Service.objects.filter(provider=obj.user, available=True)
        services_count = services.count()
        
        # Formatear el costo antes de pasarlo a format_html
        travel_cost = float(obj.avg_travel_cost or 0)
        travel_cost_formatted = f'${travel_cost:.2f}'
        
        return format_html(
            '<strong>Zonas:</strong> {}<br>'
            '<strong>Servicios:</strong> {}<br>'
            '<strong>Costo viaje:</strong> {}<br>'
            '<small style="color: #666;">{}</small>',
            zones_count if zones_count > 0 else '❌ Sin zonas',
            services_count if services_count > 0 else '❌ Sin servicios',
            travel_cost_formatted,  # Ya formateado
            obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        )
    coverage_info.short_description = 'Cobertura'
    
    def status_badge(self, obj):
        """Badge mejorado de estado"""
        colors = {
            'created': '#6c757d',
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        
        active_text = '🟢 Activo' if obj.is_active else '🔴 Inactivo'
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span><br>'
            '<small style="color: {}; font-size: 10px; margin-top: 3px; display: inline-block;">{}</small>'
            '</div>',
            color,
            obj.get_status_display(),
            '#28a745' if obj.is_active else '#dc3545',
            active_text
        )
    status_badge.short_description = 'Estado'
    
    def quick_actions(self, obj):
        """Botones de acción rápida directamente en el listado"""
        if obj.status in ['pending', 'created']:
            return format_html(
                '<div style="display: flex; flex-direction: column; gap: 3px;">'
                '<a href="{}" class="button" style="background: #28a745; color: white; text-align: center; '
                'padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 11px;">✅ Aprobar</a>'
                '<a href="{}" class="button" style="background: #dc3545; color: white; text-align: center; '
                'padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 11px;">❌ Rechazar</a>'
                '</div>',
                reverse('admin:quick_approve_provider', args=[obj.pk]),
                reverse('admin:quick_reject_provider', args=[obj.pk])
            )
        elif obj.status == 'approved':
            return format_html(
                '<div style="text-align: center; color: #28a745; font-weight: bold;">✓ Aprobado</div>'
            )
        else:
            return format_html(
                '<div style="text-align: center; color: #dc3545;">✗ Rechazado</div>'
            )
    quick_actions.short_description = 'Acciones'
    
    def rating(self, obj):
        from django.db.models import Avg
        avg = Review.objects.filter(booking__provider=obj.user).aggregate(Avg('rating'))
        rating = avg['rating__avg'] or 0
        stars = '⭐' * int(rating)
        return f'{stars} ({rating:.1f})'
    rating.short_description = 'Calificación'
    
    def get_urls(self):
        """URLs personalizadas para acciones rápidas"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:provider_id>/quick-approve/',
                self.admin_site.admin_view(self.quick_approve_view),
                name='quick_approve_provider'
            ),
            path(
                '<int:provider_id>/quick-reject/',
                self.admin_site.admin_view(self.quick_reject_view),
                name='quick_reject_provider'
            ),
            path(
                '<int:provider_id>/detail-ajax/',
                self.admin_site.admin_view(self.provider_detail_ajax),
                name='provider_detail_ajax'
            ),
        ]
        return custom_urls + urls
    
    def quick_approve_view(self, request, provider_id):
        """Vista para aprobación rápida"""
        try:
            provider_profile = ProviderProfile.objects.get(pk=provider_id)
            
            # Actualizar status
            provider_profile.status = 'approved'
            provider_profile.save()
            
            # Crear notificación
            Notification.objects.create(
                user=provider_profile.user,
                notification_type='booking_accepted',
                title='🎉 ¡Perfil Aprobado!',
                message='Tu perfil de proveedor ha sido aprobado. Configura tu cobertura, costos y horarios para empezar a recibir clientes.',
                action_url='/dashboard/'
            )
            
            # Enviar email
            try:
                from core.tasks import send_provider_approval_email_task
                send_provider_approval_email_task.delay(provider_profile_id=provider_profile.pk)
            except Exception as e:
                logger.error(f"Error enviando email de aprobación: {e}")
            
            # Log de auditoría
            AuditLog.objects.create(
                user=request.user,
                action='Proveedor aprobado (acción rápida)',
                metadata={
                    'provider_id': provider_profile.user.id,
                    'provider_username': provider_profile.user.username,
                    'category': provider_profile.category.name
                }
            )
            
            messages.success(
                request,
                f'✅ Proveedor {provider_profile.user.get_full_name()} aprobado exitosamente. Email enviado.'
            )
        except ProviderProfile.DoesNotExist:
            messages.error(request, '❌ Proveedor no encontrado')
        
        return redirect('admin:core_providerprofile_changelist')
    
    def quick_reject_view(self, request, provider_id):
        """Vista para rechazo rápido"""
        try:
            provider_profile = ProviderProfile.objects.get(pk=provider_id)
            provider_profile.status = 'rejected'
            provider_profile.save()
            
            # Notificación
            Notification.objects.create(
                user=provider_profile.user,
                notification_type='booking_cancelled',
                title='❌ Perfil Rechazado',
                message='Tu perfil de proveedor no ha sido aprobado. Por favor contacta con soporte para más información.',
                action_url='/dashboard/'
            )
            
            messages.warning(
                request,
                f'⚠️ Proveedor {provider_profile.user.get_full_name()} rechazado.'
            )
        except ProviderProfile.DoesNotExist:
            messages.error(request, '❌ Proveedor no encontrado')
        
        return redirect('admin:core_providerprofile_changelist')
    
    def provider_detail_ajax(self, request, provider_id):
        """Vista AJAX para mostrar detalles completos en modal"""
        from django.http import JsonResponse
        
        try:
            provider = ProviderProfile.objects.select_related('user', 'category').prefetch_related('coverage_zones').get(id=provider_id)
            services = Service.objects.filter(provider=provider.user)
            
            data = {
                'name': provider.user.get_full_name() or provider.user.username,
                'email': provider.user.email,
                'phone': provider.user.profile.phone if hasattr(provider.user, 'profile') else 'N/A',
                'category': provider.category.name,
                'description': provider.description,
                'status': provider.get_status_display(),
                'is_active': provider.is_active,
                'avg_travel_cost': float(provider.avg_travel_cost or 0),
                'zones': list(provider.coverage_zones.values_list('name', flat=True)),
                'services': [
                    {
                        'name': s.name,
                        'price': float(s.base_price),
                        'duration': s.duration_minutes,
                        'available': s.available
                    } for s in services
                ],
                'documents': {
                    'contract': provider.signed_contract_url or None,
                    'id_front': provider.id_card_front or None,
                    'id_back': provider.id_card_back or None,
                },
                'created_at': provider.created_at.strftime('%d/%m/%Y %H:%M')
            }
            
            return JsonResponse(data)
        except ProviderProfile.DoesNotExist:
            return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)
    
    def changelist_view(self, request, extra_context=None):
        """Agregar contexto extra al changelist"""
        extra_context = extra_context or {}
        extra_context['pending_count'] = ProviderProfile.objects.filter(status__in=['pending', 'created']).count()
        return super().changelist_view(request, extra_context=extra_context)


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

# PAYMENTS

class PaymentRefundUtil:
    """Utilidad para procesar refunds con PayPhone"""
    
    @staticmethod
    def process_refund(payment):
        """
        Procesa un refund para un pago de PayPhone
        Retorna: (success, message)
        """
        # Solo refundar pagos completados de PayPhone
        if payment.payment_method != 'payphone':
            return False, 'Solo se pueden refundar pagos de PayPhone'
        
        if payment.status != 'completed':
            return False, f'Solo se pueden refundar pagos completados. Estado actual: {payment.get_status_display()}'
        
        # Verificar si ya fue refundado
        if payment.status == 'refunded':
            return False, 'Este pago ya fue reembolsado'
        
        # Si está en modo test, no hacer refund real
        if settings.DEBUG:
            logger.info('MODO TEST: Simulando refund')
            return True, 'Refund simulado (MODO TEST)'
        
        try:
            headers = {
                'Authorization': f'Bearer {settings.PAYPHONE_API_TOKEN}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'transactionId': payment.transaction_id,
                'clientTransactionId': str(payment.booking.id)
            }
            
            logger.info(f'Procesando refund para Payment {payment.id}')
            logger.info(f'Payload: {payload}')
            
            # Usar endpoint de refund
            refund_url = settings.PAYPHONE_URL_CONFIRM_PAYPHONE.replace('confirm', 'refund')
            
            response = requests.post(
                refund_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            logger.info(f'Respuesta de refund: {response.status_code} - {response.text}')
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('statusCode') == 0 or data.get('status') == 'Success':
                    logger.info(f'✅ Refund exitoso para Payment {payment.id}')
                    return True, 'Refund procesado exitosamente'
                else:
                    error_msg = data.get('message', 'Error desconocido')
                    logger.error(f'❌ PayPhone retornó error: {error_msg}')
                    return False, f'Error de PayPhone: {error_msg}'
            else:
                logger.error(f'❌ Error HTTP {response.status_code}: {response.text}')
                return False, f'Error de comunicación: {response.status_code}'
                
        except requests.exceptions.RequestException as e:
            logger.error(f'❌ Excepción en refund: {e}')
            return False, f'Error de conexión: {str(e)}'
        except Exception as e:
            logger.error(f'❌ Error inesperado: {e}')
            return False, f'Error inesperado: {str(e)}'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Administración de pagos con funcionalidad para validar transferencias y refunds
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
    
    actions = ['approve_payments', 'reject_payments', 'process_refunds']
    
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
    
    def approve_payments(self, request, queryset):
        """Acción masiva para aprobar pagos"""
        count = 0
        for payment in queryset.filter(status='pending_validation'):
            payment.status = 'completed'
            payment.validated_by = request.user
            payment.validated_at = timezone.now()
            payment.save()
            
            # Actualizar booking
            payment.booking.payment_status = 'paid'
            payment.booking.save()
            
            # Notificaciones
            Notification.objects.create(
                user=payment.booking.customer,
                notification_type='payment_verified',
                title='✅ Pago Verificado',
                message=f'Tu pago de ${payment.amount} ha sido confirmado.',
                booking=payment.booking,
                action_url=f'/bookings/{payment.booking.id}/'
            )
            
            count += 1
        
        self.message_user(
            request,
            f'{count} pago(s) aprobado(s) exitosamente.'
        )
    approve_payments.short_description = '✅ Aprobar pagos seleccionados'
    
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
    reject_payments.short_description = '❌ Rechazar pagos seleccionados'
    
    def process_refunds(self, request, queryset):
        """Acción para procesar refunds"""
        refund_util = PaymentRefundUtil()
        successful_refunds = 0
        failed_refunds = []
        
        for payment in queryset.filter(payment_method='payphone', status='completed'):
            success, message = refund_util.process_refund(payment)
            
            if success:
                # Actualizar estado
                payment.status = 'refunded'
                payment.notes = f'Refund procesado por {request.user.username} el {timezone.now().strftime("%d/%m/%Y %H:%M")}'
                payment.save()
                
                # Notificar al cliente
                Notification.objects.create(
                    user=payment.booking.customer,
                    notification_type='payment_received',
                    title='💰 Reembolso Procesado',
                    message=f'Tu reembolso de ${payment.amount} ha sido procesado.',
                    booking=payment.booking,
                    action_url=f'/bookings/{payment.booking.id}/'
                )
                
                # Log
                AuditLog.objects.create(
                    user=request.user,
                    action='Refund de pago procesado',
                    metadata={
                        'payment_id': payment.id,
                        'booking_id': str(payment.booking.id),
                        'amount': str(payment.amount)
                    }
                )
                
                successful_refunds += 1
            else:
                failed_refunds.append(f'Payment {payment.id}: {message}')
        
        if successful_refunds > 0:
            self.message_user(
                request,
                f'✅ {successful_refunds} refund(s) procesado(s) exitosamente.',
                django_messages.SUCCESS
            )
        
        if failed_refunds:
            error_msg = '\n'.join(failed_refunds)
            self.message_user(
                request,
                f'❌ Errores en {len(failed_refunds)} refund(s):\n{error_msg}',
                django_messages.ERROR
            )
    
    process_refunds.short_description = '💰 Procesar refund(s)'
    
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
        'booking_id',           # Cambio #1: ID corto
        'customer_name',
        'provider_name',
        'status_display',
        'payment_display',
        'incident_badge',       # Cambio #2: NUEVO - Badge de incidencia
        'scheduled_time',
        'total_cost'
    ]
    
    # Cambio #2: Agregar filtro por incidencias reportadas
    list_filter = ['status', 'payment_status', 'incident_reported', 'created_at']
    
    search_fields = ['id', 'customer__username', 'provider__username']
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'incident_details'     # Cambio #2: NUEVO - Detalles de incidencia
    )
    
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
        # Cambio #2: NUEVO - Sección de Incidencias Reportadas
        ('Incidencias Reportadas', {
            'fields': (
                'incident_reported',
                'incident_details',
                'incident_description',
                'incident_reported_at'
            ),
            'classes': ('collapse',),
            'description': 'Gestión de incidencias reportadas por clientes'
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Cambio #1: Mostrar ID corto en listado
    def booking_id(self, obj):
        return f'#{obj.booking_id}'
    booking_id.short_description = 'ID Reserva'
    
    # Cambio #2: NUEVO - Método para mostrar badge de incidencia
    def incident_badge(self, obj):
        """
        Muestra un badge visual distintivo para reservas con incidencias reportadas.
        Facilita la identificación rápida de problemas en el listado.
        """
        if obj.incident_reported:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 5px 10px; '
                'border-radius: 12px; font-weight: bold; font-size: 11px; display: inline-block;">'
                '<i class="fas fa-flag"></i> INCIDENCIA</span>'
            )
        return format_html(
            '<span style="color: #6c757d; font-size: 11px;">✓ OK</span>'
        )
    incident_badge.short_description = 'Estado Incidencia'
    
    # Cambio #2: NUEVO - Método para mostrar detalles de incidencia
    def incident_details(self, obj):
        """
        Muestra los detalles completos de la incidencia en el formulario de edición.
        Proporciona un panel destacado en rojo con toda la información del problema.
        """
        if obj.incident_reported:
            return format_html(
                '<div style="background-color: #f8d7da; border: 2px solid #f5c6cb; '
                'padding: 15px; border-radius: 4px; margin: 10px 0;">'
                '<strong style="color: #721c24; font-size: 14px;">'
                '<i class="fas fa-exclamation-triangle"></i> ⚠️ INCIDENCIA REPORTADA</strong>'
                '<hr style="border-color: #f5c6cb; margin: 10px 0;">'
                '<p style="margin: 10px 0; color: #721c24; font-size: 13px; line-height: 1.5;">'
                '<strong>Descripción:</strong><br>{}</p>'
                '<p style="margin: 10px 0; color: #721c24; font-size: 12px;">'
                '<i class="fas fa-clock"></i> <strong>Reportado:</strong> {}</p>'
                '<div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid #f5c6cb;">'
                '<small style="color: #721c24;">'
                '💡 <strong>Acción recomendada:</strong> Contactar al cliente y resolver el incidente.'
                '</small></div></div>',
                obj.incident_description or '<em>Sin descripción proporcionada</em>',
                obj.incident_reported_at.strftime('%d/%m/%Y a las %H:%M') if obj.incident_reported_at else 'N/A'
            )
        return format_html(
            '<div style="color: #28a745; font-size: 13px; padding: 10px;">'
            '✅ <strong>Sin incidencias</strong><br>'
            '<small>Esta reserva no tiene reportes de incidentes</small>'
            '</div>'
        )
    incident_details.short_description = 'Detalles de Incidencia'
    
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
                    'verified_display', 'proof_image_thumbnail', 'created_at']
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/approve_single_payment/', self.admin_site.admin_view(self.approve_single_payment_view), name='approve-single-payment'),
        ]
        return custom_urls + urls
    
    # Método que lanza el error si no existe:
    def get_changelist_url(self):
        """Construye la URL de la vista de listado para este modelo."""
        # self.opts es la configuración del modelo (ModelOptions)
        app_label = self.opts.app_label
        model_name = self.opts.model_name
        url_name = f'admin:{app_label}_{model_name}_changelist'
        return reverse(url_name)

    def approve_single_payment_view(self, request, object_id):
        if request.method != 'GET':
            return redirect(self.get_changelist_url())
        
        try:
            proof = self.get_object(request, object_id) 
        except Exception:
            self.message_user(request, "Pago no encontrado.", level=messages.ERROR)
            # Redirección de fallback, aunque deberíamos usar la correcta
            return redirect(self.get_changelist_url()) 

        if proof.verified:
            self.message_user(request, f"El pago #{proof.id} ya estaba aprobado.", level=messages.INFO)
            # Utiliza la redirección correcta aquí
            return redirect(self.get_changelist_url()) 

        # --- Lógica de Aprobación ---
        proof.verified = True
        proof.verified_by = request.user
        proof.verified_at = timezone.now()
        proof.save()
        
        booking = proof.booking
        booking.payment_status = 'paid'
        booking.save()
        
        self.message_user(request, f'✅ Pago #{proof.id} aprobado exitosamente.', level=messages.SUCCESS)
        
        # 1. Ejecuta la redirección correcta
        return redirect(self.get_changelist_url())

    def booking_link(self, obj):
        # Si ya está aprobado, solo muestra el texto
        if obj.verified:
            return format_html('<strong>#{}</strong> (Aprobado)', str(obj.booking.id)[:8])
        
        # URL al método que creamos: /admin/app/proofofpayment/<id>/approve_single_payment/
        approve_url = reverse('admin:approve-single-payment', args=[obj.pk]) 
        
        # Dibuja el botón con la URL
        return format_html(
            '<strong>#{}</strong><br><a href="{}" class="button" style="margin-top: 5px;">Aprobar</a>',
            str(obj.booking.id)[:8],
            approve_url
        )
    booking_link.short_description = 'Reserva / Acción'


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
    
@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'country', 'is_active_display', 'created_at']
    list_filter = ['is_active', 'country']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at']
    
    def is_active_display(self, obj):
        return format_html('✅ Activo' if obj.is_active else '❌ Inactivo')
    is_active_display.short_description = 'Estado'

@admin.register(ProviderBankAccount)
class ProviderBankAccountAdmin(admin.ModelAdmin):
    list_display = ['provider', 'bank', 'account_number_masked', 'owner_fullname', 'is_primary', 'created_at']
    list_filter = ['bank', 'is_primary', 'account_type']
    search_fields = ['provider__username', 'owner_fullname', 'bank__name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['bank']  # Para búsqueda rápida
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('provider', 'bank', 'account_type', 'country')
        }),
        ('Datos de Cuenta', {
            'fields': ('owner_fullname', 'account_number_masked', 'account_number_encrypted')
        }),
        ('Configuración', {
            'fields': ('is_primary',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    search_fields = ['provider__username', 'owner_fullname', 'bank__name']

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['withdrawal_id', 'provider_name', 'requested_amount', 'commission_amount', 'amount_payable', 'status_badge', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['provider__username', 'provider__email', 'id']
    date_hierarchy = 'created_at'
    readonly_fields = ['id', 'commission_amount', 'amount_payable', 'created_at', 'updated_at', 'processed_by']
    actions = ['mark_as_completed', 'mark_as_rejected']
    
    fieldsets = (
        ('Solicitud', {
            'fields': ('id', 'provider', 'provider_bank_account', 'description')
        }),
        ('Montos', {
            'fields': ('requested_amount', 'commission_percent', 'commission_amount', 'amount_payable')
        }),
        ('Procesamiento', {
            'fields': ('status', 'transfer_receipt_number', 'admin_note')
        }),
        ('Reservas Cubiertas', {
            'fields': ('covered_bookings',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'processed_by'),
            'classes': ('collapse',)
        }),
    )
    
    def withdrawal_id(self, obj):
        return str(obj.id)[:8]
    withdrawal_id.short_description = 'ID'
    
    def provider_name(self, obj):
        return obj.provider.get_full_name() or obj.provider.username
    provider_name.short_description = 'Proveedor'
    
    def status_badge(self, obj):
        colors = {'pending': 'warning', 'completed': 'success', 'rejected': 'danger'}
        color = colors.get(obj.status, 'secondary')
        return format_html(f'<span class="badge bg-{color}">{obj.get_status_display()}</span>')
    status_badge.short_description = 'Estado'
    
    def mark_as_completed(self, request, queryset):
        """Marca retiros como completados y notifica al proveedor"""
        count = 0
        for withdrawal in queryset.filter(status='pending'):
            withdrawal.status = 'completed'
            withdrawal.processed_by = request.user
            withdrawal.save()
            
            # ========================================
            # NOTIFICACIÓN EN EL CENTRO
            # ========================================
            Notification.objects.create(
                user=withdrawal.provider,
                notification_type='payment_verified',
                title='💰 Retiro Completado',
                message=f'Tu solicitud de retiro de ${withdrawal.amount_payable} ha sido procesada y completada exitosamente. Revisa tu cuenta bancaria.',
                action_url=f'/provider/withdrawals/'
            )

            # ========================================
            # EMAIL AL PROVEEDOR (ASINCRÓNICO)
            # ========================================
            try:
                from core.tasks import send_withdrawal_completed_to_provider_task
                send_withdrawal_completed_to_provider_task.delay(withdrawal_id=withdrawal.id)
            except Exception as e:
                print(f"Error enviando email al proveedor: {e}")
            
            # LOG
            AuditLog.objects.create(
                user=request.user,
                action='Retiro completado',
                metadata={
                    'withdrawal_id': str(withdrawal.id),
                    'amount': str(withdrawal.amount_payable),
                    'provider': withdrawal.provider.username
                }
            )
            count += 1
        
        self.message_user(request, f'✅ {count} retiro(s) marcado(s) como completado(s). Notificaciones enviadas al proveedor.')
    mark_as_completed.short_description = '✅ Marcar como completado'
    
    def mark_as_rejected(self, request, queryset):
        queryset.filter(status='pending').update(status='rejected', processed_by=request.user)
        self.message_user(request, 'Retiros rechazados')
    mark_as_rejected.short_description = '❌ Rechazar'