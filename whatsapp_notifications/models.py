from django.db import models


class WhatsAppLog(models.Model):
    """
    Modelo para registrar todos los mensajes enviados por WhatsApp
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('read', 'Leído'),
        ('failed', 'Fallido'),
    ]
    
    recipient = models.CharField(
        'Destinatario',
        max_length=50,
        help_text='Número de teléfono del destinatario'
    )
    message_type = models.CharField(
        'Tipo de Mensaje',
        max_length=50,
        help_text='Tipo de template: booking_created, booking_accepted, etc.'
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    response = models.TextField(
        'Respuesta de API',
        blank=True,
        null=True,
        help_text='Respuesta completa de la API de WhatsApp'
    )
    message_id = models.CharField(
        'ID del Mensaje',
        max_length=255,
        blank=True,
        null=True,
        help_text='ID único del mensaje retornado por WhatsApp'
    )
    error_message = models.TextField(
        'Mensaje de Error',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField('Fecha de Creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última Actualización', auto_now=True)

    class Meta:
        db_table = 'whatsapp_logs'
        verbose_name = 'Log de WhatsApp'
        verbose_name_plural = 'Logs de WhatsApp'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['message_type']),
        ]

    def __str__(self):
        return f"{self.message_type} -> {self.recipient} ({self.get_status_display()})"