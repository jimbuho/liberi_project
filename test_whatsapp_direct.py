import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings
import time

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_success(message):
    print(f"   ✅ {message}")

def print_error(message):
    print(f"   ❌ {message}")

def print_info(label, value):
    print(f"   ℹ️  {label}: {value}")

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM
RECIPIENT = '+593998981436'

# Template aprobado
TEMPLATE_SID = 'HXac888f41014603ccab8e9670a3a864cb'

print_header("🚀 TEST DE WHATSAPP - SIN MESSAGING SERVICE")
print_info("Número WhatsApp", FROM_NUMBER)
print_info("Destinatario", RECIPIENT)
print_info("Template", TEMPLATE_SID)

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Enviar mensaje directamente SIN Messaging Service
print_header("ENVÍO DE MENSAJE DE PRUEBA")

variables = {
    "1": "María García",
    "2": "Limpieza Profunda",
    "3": "test123"
}

print_info("Variables", json.dumps(variables, indent=2, ensure_ascii=False))

try:
    # Enviar mensaje SIN especificar messaging_service_sid
    message = client.messages.create(
        from_=FROM_NUMBER,
        to=f'whatsapp:{RECIPIENT}',
        content_sid=TEMPLATE_SID,
        content_variables=json.dumps(variables)
    )
    
    print_success("¡Mensaje enviado!")
    print_info("Message SID", message.sid)
    print_info("Estado inicial", message.status)
    
    # Monitorear entrega
    print_header("MONITOREO DE ENTREGA")
    
    for i in range(15):
        time.sleep(2)
        
        try:
            msg = client.messages(message.sid).fetch()
            
            if msg.status == "delivered":
                icon = "✅"
            elif msg.status == "read":
                icon = "👁️"
            elif msg.status in ["sent", "queued", "accepted"]:
                icon = "⏳"
            else:
                icon = "❌"
            
            print(f"   [{i+1:2d}/15] {icon} Estado: {msg.status.upper()}")
            
            if msg.status in ['failed', 'undelivered']:
                print_error("FALLO EN LA ENTREGA")
                print_info("Código de error", msg.error_code)
                print_info("Mensaje de error", msg.error_message)
                
                # Diagnóstico específico del error
                if msg.error_code == 63112:
                    print("\n🔍 ERROR 63112: Meta/WhatsApp Business Account deshabilitado")
                    print("\n⚠️  CAUSAS POSIBLES:")
                    print("   1. Tu WhatsApp Business Account fue deshabilitado por Meta")
                    print("   2. Necesitas verificar tu negocio en Facebook Business Manager")
                    print("   3. Violación de políticas de WhatsApp")
                    print("   4. Cuenta de prueba expirada")
                    
                    print("\n📋 ACCIONES REQUERIDAS:")
                    print("   1. Ve a: https://business.facebook.com/")
                    print("   2. Verifica el estado de tu WhatsApp Business Account")
                    print("   3. Ve a: WhatsApp Accounts > Liberi App")
                    print("   4. Revisa si hay alguna notificación o advertencia")
                    print("   5. Verifica que tu cuenta de negocio esté verificada")
                    
                    print("\n🔗 ENLACES ÚTILES:")
                    print("   • Facebook Business Manager: https://business.facebook.com/")
                    print("   • WhatsApp Business API: https://business.facebook.com/wa/manage/home/")
                    print("   • Twilio Console: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
                    
                break
            
            if msg.status in ['delivered', 'read']:
                print("\n" + "="*80)
                print("  🎉 ¡ÉXITO! MENSAJE ENTREGADO")
                print("="*80)
                print_success("WhatsApp en PRODUCCIÓN funcionando correctamente")
                print_success(f"Revisa tu WhatsApp ({RECIPIENT})")
                break
                
        except Exception as e:
            print_error(f"Error al verificar estado: {e}")
            break
    
except TwilioRestException as e:
    print_error("ERROR DE TWILIO API")
    print_info("Código", e.code)
    print_info("Mensaje", e.msg)
    
    if e.code == 21606:
        print("\n💡 El número FROM no puede enviar a este destinatario")
        print("   Verifica que el número destinatario esté en la lista permitida")
    elif e.code == 63016:
        print("\n💡 El template no está aprobado o el SID es incorrecto")
    elif e.code == 63024:
        print("\n💡 Las variables del template no coinciden")
    
except Exception as e:
    print_error(f"ERROR GENERAL: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("  ✅ TEST COMPLETADO")
print("="*80)
