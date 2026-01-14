import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*70)
print("🔍 INFORMACIÓN DEL SANDBOX DE WHATSAPP")
print("="*70)

print("\n📱 NÚMERO DEL SANDBOX DE TWILIO:")
print("-"*70)
print("\n   El número del Sandbox de WhatsApp de Twilio es:")
print("   📞 +1 415 523 8886")
print("\n   Este es el número que debes usar en TWILIO_WHATSAPP_FROM")

print("\n📋 PASOS PARA CONFIGURAR:")
print("-"*70)
print("\n1. Actualiza tu archivo .env:")
print("   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886")

print("\n2. Activa tu número de prueba (+593998981436):")
print("   a) Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
print("   b) Encuentra tu código de activación (ej: 'join plan-cover')")
print("   c) Desde WhatsApp, envía ese código a: +1 415 523 8886")
print("   d) Espera la confirmación de Twilio")

print("\n3. Ejecuta el test nuevamente:")
print("   python test_whatsapp_final.py")

print("\n" + "="*70)
print("ℹ️  IMPORTANTE:")
print("="*70)
print("\nEl número +13853344436 que tienes es un número regular de Twilio")
print("para SMS/Voice, pero NO está habilitado para WhatsApp.")
print("\nPara usar WhatsApp necesitas:")
print("  • Sandbox (gratis, para desarrollo): +1 415 523 8886")
print("  • O un número de WhatsApp Business (requiere aprobación de Meta)")

print("\n" + "="*70)
print("🎯 CONFIGURACIÓN ACTUAL:")
print("="*70)
print(f"\nTWILIO_WHATSAPP_FROM actual: {settings.TWILIO_WHATSAPP_FROM}")
print(f"\n❌ Este número NO es válido para WhatsApp")
print(f"✅ Cambia a: whatsapp:+14155238886")

print("\n" + "="*70)
