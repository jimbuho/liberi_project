import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from twilio.rest import Client
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
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM

# El Messaging Service que acabamos de crear
MESSAGING_SERVICE_SID = "MGd0abffe4fd860cbab7e6f3c7496a78b1"

print_header("🔗 ASOCIAR NÚMERO DE WHATSAPP AL MESSAGING SERVICE")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

print_info("Messaging Service SID", MESSAGING_SERVICE_SID)
print_info("Número WhatsApp", FROM_NUMBER)

# Limpiar el formato del número
clean_number = FROM_NUMBER.replace('whatsapp:', '')
print_info("Número limpio", clean_number)

# Método 1: Intentar agregar directamente por número
print_header("MÉTODO 1: Agregar número directamente")

try:
    phone_number = client.messaging.v1.services(MESSAGING_SERVICE_SID) \
        .phone_numbers.create(phone_number_sid=clean_number)
    
    print_success(f"¡Número asociado exitosamente!")
    print_info("Phone Number SID", phone_number.sid)
    
except Exception as e:
    print_error(f"Método 1 falló: {e}")
    
    # Método 2: Buscar el SID del número primero
    print_header("MÉTODO 2: Buscar SID del número primero")
    
    try:
        # Buscar en números entrantes
        incoming_numbers = client.incoming_phone_numbers.list(
            phone_number=clean_number
        )
        
        if incoming_numbers:
            number_sid = incoming_numbers[0].sid
            print_success(f"Número encontrado!")
            print_info("Number SID", number_sid)
            
            # Intentar asociar con el SID
            phone_number = client.messaging.v1.services(MESSAGING_SERVICE_SID) \
                .phone_numbers.create(phone_number_sid=number_sid)
            
            print_success(f"¡Número asociado exitosamente!")
            print_info("Phone Number SID", phone_number.sid)
            
        else:
            print_error("Número no encontrado en incoming_phone_numbers")
            
            # Método 3: Buscar en todos los números de la cuenta
            print_header("MÉTODO 3: Listar todos los números de la cuenta")
            
            all_numbers = client.incoming_phone_numbers.list(limit=50)
            print_info("Total números encontrados", len(all_numbers))
            
            for num in all_numbers:
                print_info(f"  - {num.phone_number}", num.sid)
                if num.phone_number == clean_number or num.phone_number == FROM_NUMBER:
                    print_success(f"¡Encontrado! Intentando asociar...")
                    try:
                        phone_number = client.messaging.v1.services(MESSAGING_SERVICE_SID) \
                            .phone_numbers.create(phone_number_sid=num.sid)
                        print_success(f"¡Número asociado exitosamente!")
                        break
                    except Exception as e3:
                        print_error(f"Error al asociar: {e3}")
            
    except Exception as e2:
        print_error(f"Método 2 falló: {e2}")
        
        # Método 4: Configuración manual
        print_header("CONFIGURACIÓN MANUAL REQUERIDA")
        print("\n⚠️  No se pudo asociar el número automáticamente.")
        print("   Por favor, sigue estos pasos:")
        print("\n   1. Ve a: https://console.twilio.com/us1/develop/sms/services")
        print(f"   2. Busca el servicio: 'Liberi WhatsApp Service'")
        print(f"      (SID: {MESSAGING_SERVICE_SID})")
        print("   3. Haz clic en el servicio")
        print("   4. Ve a la pestaña 'Sender Pool' o 'Add Senders'")
        print(f"   5. Agrega el número: {clean_number}")
        print("   6. Guarda los cambios")
        print("\n   Luego ejecuta: python verify_messaging_service.py")

# Verificar la configuración final
print_header("VERIFICACIÓN FINAL")

try:
    # Listar números asociados al servicio
    phone_numbers = client.messaging.v1.services(MESSAGING_SERVICE_SID).phone_numbers.list()
    
    if phone_numbers:
        print_success(f"Números asociados al servicio:")
        for pn in phone_numbers:
            print_info("  - Número", pn.phone_number)
            if hasattr(pn, 'capabilities'):
                print_info("    Capabilities", pn.capabilities)
        
        print("\n" + "="*80)
        print("  🎉 ¡CONFIGURACIÓN COMPLETADA!")
        print("="*80)
        
        print("\n📋 PRÓXIMOS PASOS:")
        print(f"   1. Agrega a tu .env:")
        print(f"      TWILIO_MESSAGING_SERVICE_SID={MESSAGING_SERVICE_SID}")
        print("\n   2. Ejecuta el test de WhatsApp:")
        print("      python test_whatsapp.py")
    else:
        print_error("No hay números asociados al servicio aún")
        print("\n⚠️  ACCIÓN REQUERIDA:")
        print("   Ve a: https://console.twilio.com/us1/develop/sms/services")
        print(f"   Y agrega el número {clean_number} al servicio manualmente")
        
except Exception as e:
    print_error(f"Error al verificar: {e}")

print("\n" + "="*80)
