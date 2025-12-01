from django.apps import AppConfig


class WhatsappNotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.whatsapp_notifications'
    verbose_name = 'Notificaciones WhatsApp'

    def ready(self):
        import whatsapp_notifications.signals