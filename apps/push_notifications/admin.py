from django.contrib import admin
from django.utils.html import format_html
from .models import PushSubscription, PushNotificationLog


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'player_id_short',
        'device_type',
        'is_active_badge',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'device_type',
        'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'player_id',
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    date_hierarchy = 'created_at'
    
    ordering = ['-created_at']
    
    def player_id_short(self, obj):
        """Versión corta del player_id"""
        if len(obj.player_id) > 30:
            return f"{obj.player_id[:30]}..."
        return obj.player_id
    player_id_short.short_description = 'Player ID'
    
    def is_active_badge(self, obj):
        """Badge visual para el estado"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: green; color: white; padding: 4px 10px; '
                'border-radius: 4px; font-weight: bold;">✓ Activo</span>'
            )
        else:
            return format_html(
                '<span style="background-color: gray; color: white; padding: 4px 10px; '
                'border-radius: 4px;">✕ Inactivo</span>'
            )
    is_active_badge.short_description = 'Estado'


@admin.register(PushNotificationLog)
class PushNotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'notification_type',
        'title_short',
        'status_badge',
        'onesignal_id_short',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'notification_type',
        'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'title',
        'message',
        'onesignal_id',
    ]
    
    readonly_fields = [
        'user',
        'player_ids',
        'notification_type',
        'title',
        'message',
        'data',
        'status',
        'onesignal_id',
        'response',
        'error_message',
        'created_at',
        'updated_at',
    ]
    
    date_hierarchy = 'created_at'
    
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información del Envío', {
            'fields': (
                'user',
                'player_ids',
                'notification_type',
                'title',
                'message',
                'data',
            )
        }),
        ('Estado del Envío', {
            'fields': (
                'status',
                'onesignal_id',
                'response',
                'error_message',
            )
        }),
        ('Fechas', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Badge visual para el estado"""
        colors = {
            'pending': 'orange',
            'sent': 'blue',
            'delivered': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        
        icons = {
            'pending': '⏳',
            'sent': '📤',
            'delivered': '✅',
            'failed': '❌',
        }
        icon = icons.get(obj.status, '•')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">'
            '{} {}'
            '</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def title_short(self, obj):
        """Versión corta del título"""
        if len(obj.title) > 50:
            return f"{obj.title[:50]}..."
        return obj.title
    title_short.short_description = 'Título'
    
    def onesignal_id_short(self, obj):
        """Versión corta del OneSignal ID"""
        if obj.onesignal_id:
            if len(obj.onesignal_id) > 20:
                return f"{obj.onesignal_id[:20]}..."
            return obj.onesignal_id
        return '—'
    onesignal_id_short.short_description = 'ID OneSignal'
    
    def has_add_permission(self, request):
        """No permitir agregar logs manualmente"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar logs"""
        return request.user.is_superuser
