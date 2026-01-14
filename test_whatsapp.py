import os
import django
import time
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_section(number, title):
    print(f"\n{'='*80}")
    print(f"  {number}️⃣  {title}")
    print(f"{'='*80}")

def print_info(label, value):
    print(f"   ℹ️  {label}: {value}")

def print_success(message):
    print(f"   ✅ {message}")

def print_error(message):
    print(f"   ❌ {message}")

def print_warning(message):
    print(f"   ⚠️  {message}")

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM
RECIPIENT = '+593998981436'  # Tu número de prueba

# Template aprobado para producción
TEMPLATE_SID = 'HXac888f41014603ccab8e9670a3a864cb'  # booking_accepted
TEMPLATE_NAME = 'booking_accepted'

print_header("🚀 TEST DE WHATSAPP - MODO PRODUCCIÓN")
print_info("Fecha/Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
print_info("Destinatario", RECIPIENT)
print_info("Template", TEMPLATE_NAME)
print_info("Template SID", TEMPLATE_SID)

# Inicializar cliente
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# PASO 1: Verificar cuenta Twilio
print_section("1", "VERIFICACIÓN DE CUENTA TWILIO")
try:
    account = client.api.accounts(ACCOUNT_SID).fetch()
    print_success(f"Cuenta: {account.friendly_name}")
    print_success(f"Estado: {account.status}")
    print_success(f"Tipo: {account.type}")
except Exception as e:
    print_error(f"No se pudo verificar la cuenta: {e}")
    print("\n⚠️  ACCIÓN REQUERIDA:")
    print("   1. Ve a: https://console.twilio.com/")
    print("   2. Verifica que tu cuenta esté activa")
    print("   3. Toma un screenshot del dashboard principal")
    exit(1)

# PASO 2: Verificar número de WhatsApp
print_section("2", "VERIFICACIÓN DEL NÚMERO DE WHATSAPP")
try:
    incoming_phone_numbers = client.incoming_phone_numbers.list(
        phone_number=FROM_NUMBER.replace('whatsapp:', '')
    )
    
    if incoming_phone_numbers:
        number = incoming_phone_numbers[0]
        print_success(f"Número encontrado: {number.phone_number}")
        print_success(f"Friendly Name: {number.friendly_name}")
        print_success(f"Capabilities: {number.capabilities}")
    else:
        print_warning("Número no encontrado en la lista de números entrantes")
        print_warning("Esto es normal para números de WhatsApp Business API")
    
    print_success(f"Número configurado: {FROM_NUMBER}")
    
except Exception as e:
    print_warning(f"No se pudo verificar el número: {e}")
    print_warning("Continuando con el test...")

# PASO 3: Verificar template
print_section("3", "VERIFICACIÓN DEL TEMPLATE")
try:
    # Listar templates aprobados usando v1 API
    contents = client.content.v1.contents.list(limit=50)
    
    template_found = False
    approved_templates = []
    
    for content in contents:
        # El SID del template es el identificador principal
        approved_templates.append({
            'sid': content.sid,
            'name': content.friendly_name if hasattr(content, 'friendly_name') else 'N/A',
            'language': content.language if hasattr(content, 'language') else 'N/A'
        })
        
        if content.sid == TEMPLATE_SID:
            template_found = True
            print_success(f"Template encontrado!")
            print_success(f"SID: {content.sid}")
            if hasattr(content, 'friendly_name'):
                print_success(f"Nombre: {content.friendly_name}")
            if hasattr(content, 'language'):
                print_success(f"Idioma: {content.language}")
    
    if not template_found:
        print_warning(f"Template {TEMPLATE_SID} no encontrado en la lista")
        print("\n📋 Templates disponibles:")
        for t in approved_templates[:10]:  # Mostrar solo los primeros 10
            print(f"   • {t['name']} (SID: {t['sid']}, Lang: {t['language']})")
        
        print("\n⚠️  NOTA: Continuaremos con el test de envío")
        print("   Si el template está aprobado en Twilio, el envío debería funcionar")
        
except Exception as e:
    print_error(f"Error al verificar templates: {e}")
    print("\n⚠️  ACCIÓN REQUERIDA:")
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/content-editor")
    print("   2. Verifica que tengas templates aprobados")
    print("   3. Toma un screenshot de la lista de templates")
    exit(1)

# PASO 4: Enviar mensaje de prueba
print_section("4", "ENVÍO DE MENSAJE DE PRUEBA")

# Variables del template
variables = {
    "1": "María García",      # Nombre del proveedor
    "2": "Limpieza Profunda",  # Nombre del servicio
    "3": "test123"             # Booking ID para URL
}

print_info("Desde", FROM_NUMBER)
print_info("Para", f"whatsapp:{RECIPIENT}")
print_info("Variables", json.dumps(variables, indent=2, ensure_ascii=False))

try:
    message = client.messages.create(
        from_=FROM_NUMBER,
        to=f'whatsapp:{RECIPIENT}',
        content_sid=TEMPLATE_SID,
        content_variables=json.dumps(variables)
    )
    
    print_success("¡Mensaje enviado!")
    print_info("Message SID", message.sid)
    print_info("Estado inicial", message.status)
    print_info("Precio", f"${message.price} {message.price_unit}" if message.price else "N/A")
    
except TwilioRestException as e:
    print_error("ERROR DE TWILIO API")
    print_info("Código de error", e.code)
    print_info("Mensaje", e.msg)
    
    print("\n⚠️  DIAGNÓSTICO DEL ERROR:")
    
    if e.code == 63016:
        print("   • El template no está aprobado o el SID es incorrecto")
        print("\n   ACCIÓN REQUERIDA:")
        print("   1. Ve a: https://console.twilio.com/us1/develop/sms/content-editor")
        print("   2. Verifica el estado del template")
        print("   3. Copia el Content SID exacto")
        
    elif e.code == 63024:
        print("   • Las variables del template no coinciden")
        print("\n   ACCIÓN REQUERIDA:")
        print("   1. Ve al template en Twilio Console")
        print("   2. Verifica cuántas variables {{1}}, {{2}}, etc. tiene")
        print("   3. Toma un screenshot del contenido del template")
        
    elif e.code == 21608:
        print("   • El número FROM no está registrado correctamente")
        print("\n   ACCIÓN REQUERIDA:")
        print("   1. Ve a: https://console.twilio.com/us1/develop/sms/senders")
        print("   2. Verifica tu número de WhatsApp")
        print("   3. Toma un screenshot de la configuración")
        
    elif e.code == 63051:
        print("   • El número destinatario no está en la lista permitida")
        print("\n   ACCIÓN REQUERIDA:")
        print("   1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sender")
        print("   2. Agrega el número a la lista de destinatarios permitidos")
        print("   3. Toma un screenshot de la configuración")
        
    else:
        print(f"   • Error desconocido: {e.code}")
        print("\n   ACCIÓN REQUERIDA:")
        print("   1. Ve a: https://www.twilio.com/docs/api/errors")
        print(f"   2. Busca el código de error: {e.code}")
        print("   3. Toma un screenshot del error en Twilio Console")
    
    exit(1)
    
except Exception as e:
    print_error(f"ERROR GENERAL: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# PASO 5: Monitorear entrega
print_section("5", "MONITOREO DE ENTREGA")
print_info("Duración", "30 segundos (15 checks cada 2s)")

for i in range(15):
    time.sleep(2)
    
    try:
        msg = client.messages(message.sid).fetch()
        
        # Iconos según estado
        if msg.status == "delivered":
            icon = "✅"
        elif msg.status == "read":
            icon = "👁️"
        elif msg.status in ["sent", "queued", "accepted"]:
            icon = "⏳"
        else:
            icon = "❌"
        
        print(f"   [{i+1:2d}/15] {icon} Estado: {msg.status.upper()}")
        
        # Verificar si falló
        if msg.status in ['failed', 'undelivered']:
            print_error("FALLO EN LA ENTREGA")
            print_info("Código de error", msg.error_code)
            print_info("Mensaje de error", msg.error_message)
            
            print("\n⚠️  ACCIÓN REQUERIDA:")
            print("   1. Ve a: https://console.twilio.com/us1/monitor/logs/sms")
            print(f"   2. Busca el mensaje SID: {message.sid}")
            print("   3. Revisa los detalles del error")
            print("   4. Toma un screenshot del log completo")
            break
        
        # Verificar si se entregó
        if msg.status in ['delivered', 'read']:
            print("\n" + "="*80)
            print("   🎉 ¡ÉXITO! MENSAJE ENTREGADO")
            print("="*80)
            print_success("WhatsApp en PRODUCCIÓN funcionando correctamente")
            print_success(f"Revisa tu WhatsApp ({RECIPIENT}) para ver el mensaje")
            print_success("El sistema está listo para enviar notificaciones reales")
            
            print("\n📱 PRÓXIMOS PASOS:")
            print("   1. Verifica que el mensaje llegó correctamente")
            print("   2. Confirma que las variables se reemplazaron bien")
            print("   3. Prueba hacer clic en el enlace del mensaje")
            print("   4. Si todo funciona, el sistema está listo para producción")
            break
            
    except Exception as e:
        print_error(f"Error al verificar estado: {e}")
        break

print("\n" + "="*80)
print("  ✅ TEST COMPLETADO")
print("="*80)
print("\n💡 Si necesitas ayuda, proporciona:")
print("   • Screenshots de Twilio Console")
print("   • El código de error (si hubo)")
print("   • El Message SID para revisar logs")
