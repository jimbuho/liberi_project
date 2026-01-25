from django.db import models
from django.contrib.auth.models import User


class PushSubscription(models.Model):
    """
    Almacena los Player IDs de OneSignal para cada usuario
    Un usuario puede tener múltiples dispositivos suscritos
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    player_id = models.CharField(
        'Player ID de OneSignal',
        max_length=255,
        unique=True,
        help_text='ID único del dispositivo en OneSignal'
    )
    device_type = models.CharField(
        'Tipo de Dispositivo',
        max_length=50,
        blank=True,
        help_text='Web, Android, iOS, etc.'
    )
    is_active = models.BooleanField(
        'Activo',
        default=True,
        help_text='Desactivar si el usuario desuscribe'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'push_subscriptions'
        verbose_name = 'Suscripción Push'
        verbose_name_plural = 'Suscripciones Push'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['player_id']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.player_id[:20]}..."


class PushNotificationLog(models.Model):
    """
    Registro de todas las notificaciones push enviadas
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('failed', 'Fallido'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_logs',
        null=True,
        blank=True
    )
    player_ids = models.JSONField(
        'Player IDs',
        help_text='Lista de player_ids a los que se envió'
    )
    notification_type = models.CharField(
        'Tipo de Notificación',
        max_length=50,
        help_text='booking_created, booking_accepted, etc.'
    )
    title = models.CharField('Título', max_length=255)
    message = models.TextField('Mensaje')
    data = models.JSONField(
        'Datos Adicionales',
        blank=True,
        null=True,
        help_text='Data payload para la notificación'
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    onesignal_id = models.CharField(
        'ID de OneSignal',
        max_length=255,
        blank=True,
        null=True,
        help_text='ID de la notificación retornado por OneSignal'
    )
    response = models.TextField(
        'Respuesta de API',
        blank=True,
        null=True
    )
    error_message = models.TextField(
        'Mensaje de Error',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'push_notification_logs'
        verbose_name = 'Log de Notificación Push'
        verbose_name_plural = 'Logs de Notificaciones Push'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else "Broadcast"
        return f"{self.notification_type} -> {user_info} ({self.get_status_display()})"
