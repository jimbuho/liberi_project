import os
import django
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

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN

# Número SMS de Twilio (el que tienes en la imagen)
SMS_FROM = '+13853344436'

# Tus números para probar
TEST_NUMBERS = [
    '+593998981436',
    '+593958840107'
]

print_header("📱 TEST DE SMS CON TWILIO")
print_info("Número SMS (FROM)", SMS_FROM)
print_info("Números a probar", ", ".join(TEST_NUMBERS))

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Mensaje de prueba
message_body = """
🎉 ¡Hola desde Liberi App!

Este es un mensaje de prueba de SMS.

✅ Si recibes este mensaje, significa que SMS está funcionando correctamente.

📱 Liberi App - Tu plataforma de confianza
""".strip()

for recipient in TEST_NUMBERS:
    print_header(f"ENVIANDO SMS A: {recipient}")
    
    try:
        # Enviar SMS
        message = client.messages.create(
            from_=SMS_FROM,
            to=recipient,
            body=message_body
        )
        
        print_success("¡SMS enviado!")
        print_info("Message SID", message.sid)
        print_info("Estado inicial", message.status)
        print_info("Dirección", f"{SMS_FROM} → {recipient}")
        
        # Monitorear entrega
        print("\n   🔍 Monitoreando entrega (10 checks)...")
        
        for i in range(10):
            time.sleep(2)
            
            try:
                msg = client.messages(message.sid).fetch()
                
                if msg.status == "delivered":
                    icon = "✅"
                elif msg.status in ["sent", "queued", "accepted"]:
                    icon = "⏳"
                else:
                    icon = "❌"
                
                print(f"   [{i+1:2d}/10] {icon} Estado: {msg.status.upper()}", end="")
                
                if msg.error_code:
                    print(f" | Error: {msg.error_code}")
                    print_error(f"Mensaje de error: {msg.error_message}")
                    break
                else:
                    print()
                
                if msg.status in ['failed', 'undelivered']:
                    print_error(f"FALLO EN LA ENTREGA")
                    break
                
                if msg.status == 'delivered':
                    print("\n" + "="*80)
                    print(f"  🎉 ¡SMS ENTREGADO A {recipient}!")
                    print("="*80)
                    print_success("SMS funcionando correctamente")
                    print_success(f"Revisa tu teléfono {recipient}")
                    
                    if msg.price:
                        print_info("Costo", f"${abs(float(msg.price))} {msg.price_unit}")
                    
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
            print_error("El número FROM no está verificado o no tiene capacidad SMS")
        elif e.code == 21614:
            print_error("Número destinatario no es válido para SMS")
        
        print("\n" + "-"*80)
        
    except Exception as e:
        print_error(f"ERROR GENERAL: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "-"*80)

print_header("📋 RESUMEN")
print("\n   ✅ Si los SMS fueron entregados:")
print("   → ¡Perfecto! Podemos cambiar a SMS")
print("   → Actualizaremos la configuración de Liberi")
print("   → Las notificaciones llegarán por SMS en lugar de WhatsApp")
print("\n   📊 Ventajas de SMS:")
print("   • No depende de Facebook/Meta")
print("   • Entrega inmediata y confiable")
print("   • No requiere templates aprobados")
print("   • Funciona con cualquier teléfono")
print("   • Más económico (aprox $0.0075 por SMS)")

print("\n" + "="*80)
print("  ✅ TEST COMPLETADO")
print("="*80)
