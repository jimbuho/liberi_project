from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import WhatsAppLog
from .tasks import send_whatsapp_message


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
    
    # CAMBIO: Permitir agregar logs manualmente para pruebas
    fields = [
        'recipient',
        'message_type',
        'status',
        'message_id',
        'response',
        'error_message',
        'created_at',
        'updated_at',
    ]
    
    readonly_fields = [
        'status',
        'message_id',
        'response',
        'error_message',
        'created_at',
        'updated_at',
    ]
    
    date_hierarchy = 'created_at'
    
    ordering = ['-created_at']
    
    # CAMBIO: Agregar acción de reintento
    actions = ['retry_messages']
    
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
    
    # ============================================
    # ACCIÓN: REINTENTAR MENSAJES
    # ============================================
    def retry_messages(self, request, queryset):
        """
        Acción para reintentar el envío de mensajes seleccionados.
        Reenvía los mensajes usando las variables de ejemplo según el tipo.
        """
        retried = 0
        errors = []
        
        for log in queryset:
            try:
                # Variables de ejemplo según el tipo de mensaje
                variables = self._get_template_variables(log.message_type)
                
                if not variables:
                    errors.append(f'Log {log.id}: Tipo de mensaje no soportado ({log.message_type})')
                    continue
                
                # Enviar mensaje usando Celery
                send_whatsapp_message.delay(
                    recipient=log.recipient,
                    template_name=log.message_type,
                    variables=variables
                )
                
                retried += 1
                
            except Exception as e:
                errors.append(f'Log {log.id}: {str(e)}')
        
        # Mensajes de resultado
        if retried > 0:
            self.message_user(
                request,
                f'✅ {retried} mensaje(s) encolado(s) para reintento',
                messages.SUCCESS
            )
        
        if errors:
            self.message_user(
                request,
                f'❌ Errores: {"; ".join(errors)}',
                messages.ERROR
            )
    
    retry_messages.short_description = '🔄 Reintentar mensajes seleccionados'
    
    def _get_template_variables(self, message_type):
        """
        Retorna variables de ejemplo según el tipo de mensaje
        """
        variables_map = {
            'booking_created': [
                'Cliente Prueba',
                'Servicio de Prueba',
                '20/11 14:00',
                'https://liberi.app/bookings/test'
            ],
            'booking_accepted': [
                'Proveedor Prueba',
                'Servicio de Prueba',
                'https://liberi.app/bookings/test'
            ],
            'payment_confirmed': [
                'Cliente Prueba',
                'Servicio de Prueba'
            ],
            'reminder': [
                'Servicio de Prueba',
                '14:00',
                'https://liberi.app/bookings/test'
            ],
        }
        
        return variables_map.get(message_type)
    
    def save_model(self, request, obj, form, change):
        """
        Al guardar un nuevo log manualmente, enviarlo automáticamente
        """
        if not change:  # Solo para nuevos registros
            # Guardar primero el objeto
            super().save_model(request, obj, form, change)
            
            # Obtener variables según el tipo
            variables = self._get_template_variables(obj.message_type)
            
            if variables:
                # Enviar mensaje
                send_whatsapp_message.delay(
                    recipient=obj.recipient,
                    template_name=obj.message_type,
                    variables=variables
                )
                
                self.message_user(
                    request,
                    f'✅ Mensaje de prueba encolado para {obj.recipient}',
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f'⚠️ Log creado pero tipo de mensaje no soportado: {obj.message_type}',
                    messages.WARNING
                )
        else:
            super().save_model(request, obj, form, change)
    
    # CAMBIO: Permitir agregar logs manualmente para pruebas
    def has_add_permission(self, request):
        """Permitir crear logs manualmente para pruebas"""
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar logs"""
        return request.user.is_superuser