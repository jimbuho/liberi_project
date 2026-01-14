import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.models import WhatsAppLog

print(f"WHATSAPP_TEST_MODE: {settings.WHATSAPP_TEST_MODE}")

logs = WhatsAppLog.objects.order_by('-created_at')[:5]
for log in logs:
    print(f"ID: {log.id}, Type: {log.message_type}, Status: {log.status}, Recipient: {log.recipient}, Response: {log.response}")
