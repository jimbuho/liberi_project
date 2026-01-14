import os
import django
from twilio.rest import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*70)
print("🔍 BUSCANDO NÚMERO DE WHATSAPP BUSINESS")
print("="*70)

ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
client = Client(ACCOUNT_SID, AUTH_TOKEN)

print("\n1️⃣ Buscando senders de WhatsApp configurados...")
print("-"*70)

try:
    # Intentar obtener los senders de WhatsApp
    # Nota: Esta API puede requerir permisos específicos
    
    # Método 1: Buscar en Messaging Services
    print("\n📋 Servicios de Mensajería:")
    services = client.messaging.v1.services.list(limit=20)
    
    whatsapp_found = False
    for service in services:
        print(f"\n   Servicio: {service.friendly_name}")
        print(f"   SID: {service.sid}")
        
        # Intentar obtener los senders del servicio
        try:
            senders = client.messaging.v1.services(service.sid).phone_numbers.list()
            for sender in senders:
                print(f"      📞 Sender: {sender.phone_number}")
                if 'whatsapp' in sender.capabilities:
                    print(f"         ✅ WhatsApp habilitado")
                    whatsapp_found = True
        except Exception as e:
            pass
    
    if not whatsapp_found:
        print("\n   ⚠️  No se encontraron senders de WhatsApp en servicios")
    
except Exception as e:
    print(f"   ℹ️  No se pudo acceder a servicios de mensajería: {e}")

# Método 2: Buscar en números entrantes
print("\n\n2️⃣ Números de teléfono en tu cuenta:")
print("-"*70)

try:
    incoming_numbers = client.incoming_phone_numbers.list(limit=50)
    
    for number in incoming_numbers:
        print(f"\n   📞 {number.phone_number}")
        print(f"      Nombre: {number.friendly_name}")
        print(f"      SID: {number.sid}")
        print(f"      Capacidades:")
        print(f"         SMS: {number.capabilities.get('sms', False)}")
        print(f"         MMS: {number.capabilities.get('mms', False)}")
        print(f"         Voice: {number.capabilities.get('voice', False)}")
        
        # Verificar si tiene configuración de WhatsApp
        # Los números de WhatsApp Business suelen tener webhooks específicos
        if number.sms_url and 'whatsapp' in str(number.sms_url).lower():
            print(f"         ✅ Posible número de WhatsApp")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# Método 3: Información de los templates
print("\n\n3️⃣ Verificando templates y sus configuraciones:")
print("-"*70)

TEMPLATES = settings.TWILIO_TEMPLATES

for template_name, template_info in TEMPLATES.items():
    content_sid = template_info['content_sid']
    
    try:
        content = client.content.v1.contents(content_sid).fetch()
        print(f"\n   📋 Template: {template_name}")
        print(f"      Content SID: {content_sid}")
        print(f"      Nombre: {content.friendly_name}")
        print(f"      Idioma: {content.language}")
        
        # Intentar obtener más información
        # Los templates aprobados suelen tener metadata sobre el número asociado
        
    except Exception as e:
        print(f"\n   📋 Template: {template_name}")
        print(f"      ❌ Error: {e}")

print("\n\n" + "="*70)
print("💡 RECOMENDACIONES:")
print("="*70)

print("\n1. Ve a la consola de Twilio:")
print("   https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")

print("\n2. Busca tu número de WhatsApp Business aprobado")
print("   Debería aparecer con estado 'Active' o 'Connected'")

print("\n3. Copia ese número y actualiza tu .env:")
print("   TWILIO_WHATSAPP_FROM=whatsapp:+[NUMERO_APROBADO]")

print("\n4. El número debería ser diferente a:")
print("   ❌ +14155238886 (Sandbox)")
print("   ❌ +13853344436 (Número regular)")

print("\n5. Probablemente sea un número que empiece con:")
print("   ✅ +1 (USA)")
print("   ✅ +52 (México)")
print("   ✅ +593 (Ecuador)")
print("   ✅ O el código de país que hayas configurado")

print("\n" + "="*70)
