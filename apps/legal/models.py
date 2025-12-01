from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class LegalDocument(models.Model):
    """Documentos legales del sistema (términos y privacidad)"""
    
    DOCUMENT_TYPES = [
        ('terms_user', 'Términos de Uso - Usuario'),
        ('privacy_user', 'Política de Privacidad - Usuario'),
        ('terms_provider', 'Términos de Uso - Proveedor'),
        ('privacy_provider', 'Política de Privacidad - Proveedor'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('published', 'Publicado'),
        ('archived', 'Archivado'),
    ]
    
    document_type = models.CharField(
        'Tipo de Documento',
        max_length=50,
        choices=DOCUMENT_TYPES,
        unique=True
    )
    version = models.IntegerField('Versión', default=1)
    content = models.TextField('Contenido HTML')
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    is_active = models.BooleanField(
        'Activo',
        default=False,
        help_text='Solo puede haber una versión activa por tipo de documento'
    )
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_legal_documents',
        verbose_name='Creado por'
    )
    
    class Meta:
        db_table = 'legal_documents'
        verbose_name = 'Documento Legal'
        verbose_name_plural = 'Documentos Legales'
        ordering = ['-created_at']
        unique_together = ['document_type', 'version']
    
    def __str__(self):
        return f"{self.get_document_type_display()} v{self.version} {'(Activo)' if self.is_active else ''}"
    
    def save(self, *args, **kwargs):
        """Asegurar que solo una versión del documento sea activa"""
        if self.is_active:
            LegalDocument.objects.filter(
                document_type=self.document_type,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)



class LegalAcceptance(models.Model):
    """Registro de aceptación de documentos legales por usuarios"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='legal_acceptances',
        verbose_name='Usuario'
    )
    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.PROTECT,
        related_name='acceptances',
        verbose_name='Documento'
    )
    accepted_at = models.DateTimeField(
        'Aceptado el',
        auto_now_add=True
    )
    ip_address = models.GenericIPAddressField(
        'Dirección IP',
        null=True,
        blank=True,
        help_text='IP desde donde se aceptó el documento'
    )
    user_agent = models.TextField(
        'User Agent',
        blank=True,
        help_text='Información del navegador/dispositivo'
    )
    
    # NUEVO CAMPO
    accepted_via = models.CharField(
        'Aceptado vía',
        max_length=50,
        default='web_form',
        help_text='Método de aceptación: web_form, google_oauth, etc.'
    )
    
    class Meta:
        db_table = 'legal_acceptances'
        verbose_name = 'Aceptación Legal'
        verbose_name_plural = 'Aceptaciones Legales'
        ordering = ['-accepted_at']
        unique_together = ['user', 'document']

    def __str__(self):
        return f"{self.user.username} aceptó {self.document.get_document_type_display()} v{self.document.version}"