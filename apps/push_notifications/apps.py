from django.apps import AppConfig


class PushNotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.push_notifications'
    verbose_name = 'Notificaciones Push'

    def ready(self):
        import apps.push_notifications.signals
