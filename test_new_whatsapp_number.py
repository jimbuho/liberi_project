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

# NUEVO NÚMERO DE WHATSAPP
NEW_WHATSAPP_FROM = 'whatsapp:+15557726158'

# Tu número para probar
TEST_NUMBER = '+593998981436'

# Template que ya tienes aprobado
TEMPLATE_SID = 'HXac888f41014603ccab8e9670a3a864cb'  # booking_accepted

print_header("🧪 TEST DE WHATSAPP CON NUEVO NÚMERO")
print_info("Número WhatsApp (FROM)", NEW_WHATSAPP_FROM)
print_info("Número de prueba (TO)", TEST_NUMBER)
print_info("Template", TEMPLATE_SID)

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Variables del template booking_accepted
variables = {
    "1": "María García",      # nombre_proveedor
    "2": "Limpieza Profunda", # servicio
    "3": "test123"            # booking_url
}

print_header("📤 ENVIANDO MENSAJE DE PRUEBA")

try:
    # Enviar mensaje
    message = client.messages.create(
        from_=NEW_WHATSAPP_FROM,
        to=f'whatsapp:{TEST_NUMBER}',
        content_sid=TEMPLATE_SID,
        content_variables=json.dumps(variables)
    )
    
    print_success("¡Mensaje enviado!")
    print_info("Message SID", message.sid)
    print_info("Estado inicial", message.status)
    print_info("Dirección", f"{NEW_WHATSAPP_FROM} → whatsapp:{TEST_NUMBER}")
    
    # Monitorear entrega
    print("\n   🔍 Monitoreando entrega (15 checks, 30 segundos)...")
    
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
            
            print(f"   [{i+1:2d}/15] {icon} Estado: {msg.status.upper()}", end="")
            
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
                    print_warning("Este nuevo número también está deshabilitado por Meta")
                    print("\n💡 SOLUCIÓN:")
                    print("   1. Ve a Facebook Business Manager")
                    print("   2. Verifica el estado de la cuenta")
                    print("   3. Busca notificaciones o advertencias")
                elif msg.error_code == 63051:
                    print_warning("Error 63051: Número no está en la lista permitida")
                    print_warning(f"Necesitas agregar {TEST_NUMBER} en Facebook Business Manager")
                    print("\n💡 SOLUCIÓN:")
                    print("   1. Ve a: https://business.facebook.com/wa/manage/phone-numbers/")
                    print("   2. Haz clic en el número +15557726158")
                    print("   3. Busca 'Números de prueba' o 'Test numbers'")
                    print(f"   4. Agrega {TEST_NUMBER}")
                elif msg.error_code == 63016:
                    print_warning("Error 63016: Template no encontrado o no aprobado")
                    print("\n💡 SOLUCIÓN:")
                    print("   1. Verifica que el template esté aprobado en Meta")
                    print("   2. El template debe estar en la cuenta de WhatsApp Business")
                
                break
            
            # Si se entregó, celebrar
            if msg.status in ['delivered', 'read']:
                print("\n" + "="*80)
                print(f"  🎉 ¡ÉXITO! WHATSAPP FUNCIONANDO")
                print("="*80)
                print_success("El mensaje fue entregado correctamente")
                print_success(f"Revisa tu WhatsApp en {TEST_NUMBER}")
                
                if msg.price:
                    print_info("Costo", f"${abs(float(msg.price))} {msg.price_unit}")
                
                print("\n📋 PRÓXIMOS PASOS:")
                print("   1. Actualizar TWILIO_WHATSAPP_FROM en .env")
                print(f"   2. Usar: TWILIO_WHATSAPP_FROM={NEW_WHATSAPP_FROM}")
                print("   3. Desplegar a producción")
                
                break
                
        except Exception as e:
            print_error(f"Error al verificar estado: {e}")
            break
    
    print("\n" + "-"*80)
    
except TwilioRestException as e:
    print_error("ERROR DE TWILIO API")
    print_info("Código", e.code)
    print_info("Mensaje", e.msg)
    
    if e.code == 21211:
        print_error("Número destinatario inválido")
    elif e.code == 21608:
        print_error("El número FROM no está verificado o no tiene capacidad WhatsApp")
        print("\n💡 SOLUCIÓN:")
        print("   1. Verifica que +15557726158 esté registrado en Twilio")
        print("   2. Ve a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
        print("   3. Confirma que el número aparezca como WhatsApp Sender")
    elif e.code == 63112:
        print_error("Cuenta de WhatsApp Business deshabilitada por Meta")
        print("\n💡 SOLUCIÓN:")
        print("   Contacta a soporte de Meta para reactivar la cuenta")
    
    print("\n" + "-"*80)
    
except Exception as e:
    print_error(f"ERROR GENERAL: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "-"*80)

print_header("✅ TEST COMPLETADO")
