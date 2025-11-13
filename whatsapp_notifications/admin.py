from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from .models import WhatsAppLog


@admin.register(WhatsAppLog)
class WhatsAppLogAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient',
        'message_type',
        'status_badge',
        'message_id_short',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'message_type',
        'created_at',
    ]
    
    search_fields = [
        'recipient',
        'message_id',
        'message_type',
        'error_message',
    ]
    
    readonly_fields = [
        'recipient',
        'message_type',
        'status',
        'message_id',
        'response',
        'error_message',
        'created_at',
        'updated_at',
    ]
    
    date_hierarchy = 'created_at'
    
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información del Mensaje', {
            'fields': (
                'recipient',
                'message_type',
                'status',
                'message_id',
            )
        }),
        ('Detalles Técnicos', {
            'fields': (
                'response',
                'error_message',
            ),
            'classes': ('collapse',)
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
            'read': 'darkgreen',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        
        icons = {
            'pending': '⏳',
            'sent': '📤',
            'delivered': '✅',
            'read': '✓✓',
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
    
    def message_id_short(self, obj):
        """Muestra versión corta del message_id"""
        if obj.message_id:
            if len(obj.message_id) > 20:
                return f"{obj.message_id[:20]}..."
            return obj.message_id
        return '—'
    message_id_short.short_description = 'ID Mensaje'
    
    def has_add_permission(self, request):
        """No permitir crear logs manualmente"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar logs"""
        return request.user.is_superuser