from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import LegalDocument, LegalAcceptance


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    """Administración de documentos legales"""
    
    list_display = [
        'document_type_display',
        'version',
        'status_badge',
        'is_active_badge',
        'total_acceptances',
        'created_at',
    ]
    
    list_filter = [
        'document_type',
        'status',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'document_type',
        'content'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'total_acceptances',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('document_type', 'version', 'status', 'is_active')
        }),
        ('Contenido', {
            'fields': ('content',),
            'classes': ('wide',)
        }),
        ('Control', {
            'fields': ('total_acceptances',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_active', 'make_archived']
    
    def document_type_display(self, obj):
        """Muestra el tipo de documento"""
        return obj.get_document_type_display()
    document_type_display.short_description = 'Documento'
    
    def status_badge(self, obj):
        """Badge visual para el estado"""
        colors = {
            'draft': '#FFC107',
            'published': '#28A745',
            'archived': '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def is_active_badge(self, obj):
        """Badge para indicar si es activo"""
        if obj.is_active:
            return format_html('✅ <strong>Activo</strong>')
        return format_html('⏸️ Inactivo')
    is_active_badge.short_description = 'Activo'
    
    def total_acceptances(self, obj):
        """Total de aceptaciones del documento"""
        count = obj.acceptances.count()
        url = reverse('admin:legal_legalacceptance_changelist') + f'?document__id__exact={obj.id}'
        return format_html(
            '<a href="{}">{} aceptaciones</a>',
            url,
            count
        )
    total_acceptances.short_description = 'Aceptaciones'
    
    def make_active(self, request, queryset):
        """Acción para marcar como activo"""
        for doc in queryset:
            LegalDocument.objects.filter(
                document_type=doc.document_type,
                is_active=True
            ).exclude(pk=doc.pk).update(is_active=False)
            
            doc.is_active = True
            doc.status = 'published'
            doc.save()
        
        self.message_user(request, f'{queryset.count()} documento(s) activado(s).')
    make_active.short_description = '✅ Marcar como activo'
    
    def make_archived(self, request, queryset):
        """Acción para archivar"""
        queryset.update(status='archived')
        self.message_user(request, f'{queryset.count()} documento(s) archivado(s).')
    make_archived.short_description = '📦 Archivar'


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    """Administración de aceptaciones de documentos legales"""
    
    list_display = [
        'user',
        'document_type',
        'accepted_at',
        'ip_address',
    ]
    
    list_filter = [
        'document__document_type',
        'accepted_at',
        ('user', admin.RelatedOnlyFieldListFilter)
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'ip_address',
    ]
    
    readonly_fields = [
        'user',
        'document',
        'accepted_at',
        'ip_address',
        'user_agent'
    ]
    
    fieldsets = (
        ('Información General', {
            'fields': ('user', 'document', 'accepted_at')
        }),
        ('Detalles Técnicos', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'accepted_at'
    
    def document_type(self, obj):
        """Tipo de documento aceptado"""
        return obj.document.get_document_type_display()
    document_type.short_description = 'Documento'
    
    def has_add_permission(self, request):
        """No permitir crear manualmente desde admin"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusers pueden eliminar"""
        return request.user.is_superuser