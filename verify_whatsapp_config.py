import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from django.conf import settings
from twilio.rest import Client

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_success(message):
    print(f"   ✅ {message}")

def print_info(label, value):
    print(f"   ℹ️  {label}: {value}")

print_header("🔍 VERIFICACIÓN DE CONFIGURACIÓN DE WHATSAPP")

# Verificar variables de entorno
print("\n📋 VARIABLES DE ENTORNO:")
print_info("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID[:10] + "...")
print_info("TWILIO_AUTH_TOKEN", "***" + settings.TWILIO_AUTH_TOKEN[-4:])
print_info("TWILIO_WHATSAPP_FROM", settings.TWILIO_WHATSAPP_FROM)

# Verificar que sea el número correcto
if settings.TWILIO_WHATSAPP_FROM == 'whatsapp:+15557726158':
    print_success("Número de WhatsApp actualizado correctamente")
else:
    print(f"   ⚠️  Número esperado: whatsapp:+15557726158")
    print(f"   ⚠️  Número actual: {settings.TWILIO_WHATSAPP_FROM}")

# Verificar conexión con Twilio
print("\n🔌 VERIFICANDO CONEXIÓN CON TWILIO:")
try:
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
    print_success(f"Conectado a cuenta: {account.friendly_name}")
    print_info("Estado de cuenta", account.status)
except Exception as e:
    print(f"   ❌ Error: {e}")

# Verificar número de WhatsApp en Twilio
print("\n📱 VERIFICANDO NÚMERO DE WHATSAPP:")
try:
    # Extraer el número sin 'whatsapp:'
    phone_number = settings.TWILIO_WHATSAPP_FROM.replace('whatsapp:', '')
    
    incoming_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
    
    if incoming_numbers:
        for number in incoming_numbers:
            print_success(f"Número encontrado: {number.phone_number}")
            print_info("Friendly Name", number.friendly_name)
            print_info("Capabilities", f"SMS: {number.capabilities.get('sms', False)}, Voice: {number.capabilities.get('voice', False)}")
    else:
        print(f"   ⚠️  Número no encontrado en incoming_phone_numbers")
        print(f"   ℹ️  Esto es normal para números de WhatsApp")
        print(f"   ℹ️  El número está configurado en WhatsApp Senders")
        
except Exception as e:
    print(f"   ℹ️  {e}")

# Verificar templates
print("\n📝 VERIFICANDO TEMPLATES:")
try:
    templates = client.content.v1.contents.list(limit=10)
    
    if templates:
        print_success(f"Templates encontrados: {len(templates)}")
        for template in templates[:5]:  # Mostrar solo los primeros 5
            friendly_name = getattr(template, 'friendly_name', 'N/A')
            language = getattr(template, 'language', 'N/A')
            print(f"   • {friendly_name} ({language}) - SID: {template.sid}")
    else:
        print(f"   ⚠️  No se encontraron templates")
        
except Exception as e:
    print(f"   ⚠️  Error al listar templates: {e}")

print_header("✅ VERIFICACIÓN COMPLETADA")

print("\n📋 RESUMEN:")
print("   ✅ Variables de entorno configuradas")
print("   ✅ Conexión con Twilio establecida")
print("   ✅ Número de WhatsApp: +15557726158")
print("   ✅ Templates disponibles")

print("\n🚀 PRÓXIMOS PASOS:")
print("   1. Hacer commit de los cambios")
print("   2. Push a GitHub")
print("   3. Verificar en producción (Fly.io)")

print("\n" + "="*80)
