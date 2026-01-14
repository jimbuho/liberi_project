import os
import django
import json
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings

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

def print_warning(message):
    print(f"   ⚠️  {message}")

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM
TEMPLATE_SID = 'HXac888f41014603ccab8e9670a3a864cb'  # booking_accepted

# Tus números con código de país de Ecuador
TEST_NUMBERS = [
    '+593998981436',  # Tu primer número
    '+593958840107'   # Tu segundo número
]

print_header("🧪 TEST DE WHATSAPP CON TUS NÚMEROS")
print_info("Número WhatsApp (FROM)", FROM_NUMBER)
print_info("Template", TEMPLATE_SID)
print_info("Números a probar", ", ".join(TEST_NUMBERS))

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Variables del template
variables = {
    "1": "María García",
    "2": "Limpieza Profunda",
    "3": "test123"
}

for recipient in TEST_NUMBERS:
    print_header(f"PROBANDO CON: {recipient}")
    
    try:
        # Enviar mensaje
        message = client.messages.create(
            from_=FROM_NUMBER,
            to=f'whatsapp:{recipient}',
            content_sid=TEMPLATE_SID,
            content_variables=json.dumps(variables)
        )
        
        print_success("¡Mensaje enviado!")
        print_info("Message SID", message.sid)
        print_info("Estado inicial", message.status)
        
        # Monitorear por 20 segundos
        print("\n   🔍 Monitoreando entrega (10 checks)...")
        
        for i in range(10):
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
                
                print(f"   [{i+1:2d}/10] {icon} Estado: {msg.status.upper()}", end="")
                
                if msg.error_code:
                    print(f" | Error: {msg.error_code}")
                else:
                    print()
                
                # Si falló, mostrar detalles
                if msg.status in ['failed', 'undelivered']:
                    print_error(f"\nFALLÓ CON ERROR: {msg.error_code}")
                    print_info("Mensaje de error", msg.error_message or "None")
                    
                    if msg.error_code == 63112:
                        print_warning("Error 63112: Meta/WhatsApp Business Account deshabilitado")
                        print_warning("Este número también falla con el mismo error")
                    elif msg.error_code == 63051:
                        print_warning("Error 63051: Número no está en la lista permitida")
                        print_warning(f"Necesitas agregar {recipient} en Facebook Business Manager")
                    
                    break
                
                # Si se entregó, celebrar
                if msg.status in ['delivered', 'read']:
                    print("\n" + "="*80)
                    print(f"  🎉 ¡ÉXITO CON {recipient}!")
                    print("="*80)
                    print_success("El mensaje fue entregado correctamente")
                    print_success("WhatsApp está funcionando en producción")
                    print(f"\n   📱 Revisa tu WhatsApp ({recipient}) para ver el mensaje")
                    break
                    
            except Exception as e:
                print_error(f"Error al verificar estado: {e}")
                break
        
        print("\n" + "-"*80)
        
    except TwilioRestException as e:
        print_error("ERROR DE TWILIO API")
        print_info("Código", e.code)
        print_info("Mensaje", e.msg)
        
        if e.code == 21606:
            print_warning("El número FROM no puede enviar a este destinatario")
        elif e.code == 63016:
            print_warning("El template no está aprobado o el SID es incorrecto")
        elif e.code == 63024:
            print_warning("Las variables del template no coinciden")
        
        print("\n" + "-"*80)
        
    except Exception as e:
        print_error(f"ERROR GENERAL: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "-"*80)

print_header("📋 RESUMEN DEL TEST")
print("\n   Si AMBOS números fallaron con error 63112:")
print("   → El problema es la cuenta de WhatsApp Business en Meta")
print("   → NO es problema de números no autorizados")
print("   → Meta ha deshabilitado temporalmente tu cuenta")
print("\n   Si algún número falló con error 63051:")
print("   → Ese número necesita ser agregado en Facebook Business Manager")
print("   → Ve a: Administrador de WhatsApp > Configuración")
print("   → Busca la opción para agregar números de prueba")
print("\n   Si algún mensaje fue ENTREGADO:")
print("   → ¡WhatsApp está funcionando!")
print("   → El problema era solo con el número anterior")

print("\n" + "="*80)
print("  ✅ TEST COMPLETADO")
print("="*80)
