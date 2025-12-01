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
                'template_variables',  # Campo editable para ingresar variables
                'status',
                'message_id',
            ),
            'description': 'Para enviar un mensaje de prueba, ingresa las variables en formato JSON. '
                          'Ejemplo para booking_created: ["Juan Pérez", "Corte de cabello", "20/11 14:00", "https://liberi.app/bookings/test"]'
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
        Usa las variables guardadas en el log original.
        """
        retried = 0
        errors = []
        
        for log in queryset:
            try:
                # Usar variables guardadas o valores por defecto
                if log.template_variables:
                    variables = log.template_variables
                else:
                    self.message_user(
                        request,
                        '❌ No existen variables para enviar el mensaje',
                        messages.ERROR
                    )
                    break
                
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
                f'✅ {retried} mensaje(s) encolado(s) para reintento con variables originales',
                messages.SUCCESS
            )
        
        if errors:
            self.message_user(
                request,
                f'❌ Errores: {"; ".join(errors)}',
                messages.ERROR
            )
    
    retry_messages.short_description = '🔄 Reintentar mensajes seleccionados'
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Personalizar el formulario para agregar ayuda dinámica según el tipo de mensaje
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Agregar texto de ayuda para el campo template_variables
        if 'template_variables' in form.base_fields:
            help_text = (
                '<strong>Formato JSON de variables por template:</strong><br><br>'
                '<code>booking_created</code> (4 variables):<br>'
                '<code>["Juan Pérez", "Corte de cabello", "20/11 14:00", "https://liberi.app/bookings/abc123"]</code><br><br>'
                '<code>booking_accepted</code> (3 variables):<br>'
                '<code>["María López", "Manicure", "https://liberi.app/bookings/xyz789"]</code><br><br>'
                '<code>payment_confirmed</code> (2 variables):<br>'
                '<code>["Carlos Ruiz", "Limpieza de hogar"]</code><br><br>'
                '<code>reminder</code> (3 variables):<br>'
                '<code>["Masaje relajante", "14:30", "https://liberi.app/bookings/def456"]</code><br><br>'
                '<em>Si lo dejas vacío, se usarán valores de prueba genéricos.</em>'
            )
            form.base_fields['template_variables'].help_text = help_text
        
        return form
    
    def save_model(self, request, obj, form, change):
        """
        Al guardar un nuevo log manualmente, enviarlo automáticamente
        """
        if not change:  # Solo para nuevos registros
            # Guardar primero el objeto
            super().save_model(request, obj, form, change)
            
            # SOLO enviar si el usuario especificó variables
            if obj.template_variables:
                # Usuario especificó variables manualmente
                variables = obj.template_variables
                
                # Enviar mensaje
                send_whatsapp_message.delay(
                    recipient=obj.recipient,
                    template_name=obj.message_type,
                    variables=variables
                )
                
                self.message_user(
                    request,
                    f'✅ Mensaje encolado con variables: {variables}',
                    messages.SUCCESS
                )
            else:
                # No hay variables, no enviar
                self.message_user(
                    request,
                    f'ℹ️ Log creado. Especifica "Variables del Template" en formato JSON y guarda nuevamente para enviar el mensaje.',
                    messages.INFO
                )
        else:
            # Editando log existente
            super().save_model(request, obj, form, change)
    
    # CAMBIO: Permitir agregar logs manualmente para pruebas
    def has_add_permission(self, request):
        """Permitir crear logs manualmente para pruebas"""
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar logs"""
        return request.user.is_superuser