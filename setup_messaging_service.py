import os
import django
import sys

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

def print_warning(message):
    print(f"   ⚠️  {message}")

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM

print_header("🔧 CONFIGURACIÓN DE MESSAGING SERVICE PARA WHATSAPP")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Paso 1: Verificar si ya existe un Messaging Service
print_header("PASO 1: Verificar Messaging Services existentes")

try:
    services = client.messaging.v1.services.list(limit=20)
    
    if services:
        print_success(f"Encontrados {len(services)} Messaging Service(s)")
        for service in services:
            print_info("Service SID", service.sid)
            print_info("Friendly Name", service.friendly_name)
            print_info("Status", service.status)
            
            # Verificar si tiene el número de WhatsApp asociado
            phone_numbers = client.messaging.v1.services(service.sid).phone_numbers.list()
            for pn in phone_numbers:
                print_info("  - Número asociado", pn.phone_number)
                if pn.phone_number == FROM_NUMBER.replace('whatsapp:', ''):
                    print_success(f"¡El número {FROM_NUMBER} YA está asociado a este servicio!")
                    print_info("Service SID a usar", service.sid)
                    print("\n" + "="*80)
                    print("  ✅ CONFIGURACIÓN COMPLETA")
                    print("="*80)
                    print("\n💡 Tu número ya tiene un Messaging Service configurado.")
                    print("   El problema debe ser otro. Vamos a investigar más...")
                    sys.exit(0)
    else:
        print_warning("No se encontraron Messaging Services")
        
except Exception as e:
    print_error(f"Error al listar servicios: {e}")

# Paso 2: Crear un nuevo Messaging Service
print_header("PASO 2: Crear nuevo Messaging Service")

try:
    service = client.messaging.v1.services.create(
        friendly_name='Liberi WhatsApp Service'
    )
    
    print_success("Messaging Service creado!")
    print_info("Service SID", service.sid)
    print_info("Friendly Name", service.friendly_name)
    
    # Guardar el SID para usarlo después
    messaging_service_sid = service.sid
    
except Exception as e:
    print_error(f"Error al crear Messaging Service: {e}")
    print("\n⚠️  ACCIÓN MANUAL REQUERIDA:")
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/services")
    print("   2. Haz clic en 'Create Messaging Service'")
    print("   3. Nombre: 'Liberi WhatsApp Service'")
    print("   4. Use case: 'Notifications'")
    print("   5. Toma un screenshot del proceso")
    sys.exit(1)

# Paso 3: Asociar el número de WhatsApp al Messaging Service
print_header("PASO 3: Asociar número de WhatsApp al Messaging Service")

try:
    # Limpiar el formato del número
    clean_number = FROM_NUMBER.replace('whatsapp:', '')
    
    phone_number = client.messaging.v1.services(messaging_service_sid) \
        .phone_numbers.create(phone_number_sid=clean_number)
    
    print_success(f"Número {clean_number} asociado al Messaging Service!")
    print_info("Phone Number SID", phone_number.sid)
    
except Exception as e:
    print_error(f"Error al asociar número: {e}")
    print_warning("Intentando método alternativo...")
    
    # Método alternativo: buscar el SID del número primero
    try:
        # Buscar el número en la lista de números entrantes
        incoming_numbers = client.incoming_phone_numbers.list(
            phone_number=clean_number
        )
        
        if incoming_numbers:
            number_sid = incoming_numbers[0].sid
            print_info("Número SID encontrado", number_sid)
            
            # Intentar asociar con el SID
            phone_number = client.messaging.v1.services(messaging_service_sid) \
                .phone_numbers.create(phone_number_sid=number_sid)
            
            print_success(f"Número asociado exitosamente!")
            
        else:
            print_error("No se pudo encontrar el número en la cuenta")
            print("\n⚠️  ACCIÓN MANUAL REQUERIDA:")
            print("   1. Ve a: https://console.twilio.com/us1/develop/sms/services")
            print(f"   2. Selecciona el servicio: {messaging_service_sid}")
            print("   3. Ve a 'Sender Pool'")
            print(f"   4. Agrega el número: {clean_number}")
            print("   5. Toma un screenshot del proceso")
            sys.exit(1)
            
    except Exception as e2:
        print_error(f"Error en método alternativo: {e2}")
        print("\n⚠️  ACCIÓN MANUAL REQUERIDA:")
        print("   1. Ve a: https://console.twilio.com/us1/develop/sms/services")
        print(f"   2. Selecciona el servicio creado (SID: {messaging_service_sid})")
        print("   3. Ve a la pestaña 'Sender Pool'")
        print(f"   4. Agrega el número de WhatsApp: {clean_number}")
        print("   5. Guarda los cambios")
        print("   6. Toma un screenshot cuando esté listo")
        sys.exit(1)

# Paso 4: Verificar la configuración
print_header("PASO 4: Verificar configuración final")

try:
    # Listar números asociados al servicio
    phone_numbers = client.messaging.v1.services(messaging_service_sid).phone_numbers.list()
    
    print_success(f"Números asociados al servicio:")
    for pn in phone_numbers:
        print_info("  - Número", pn.phone_number)
        print_info("    Capabilities", pn.capabilities)
    
    print("\n" + "="*80)
    print("  🎉 ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
    print("="*80)
    
    print("\n📋 INFORMACIÓN IMPORTANTE:")
    print(f"   • Messaging Service SID: {messaging_service_sid}")
    print(f"   • Número WhatsApp: {FROM_NUMBER}")
    print(f"   • Cuenta: {ACCOUNT_SID}")
    
    print("\n🔄 PRÓXIMO PASO:")
    print("   Actualiza tu archivo .env con:")
    print(f"   TWILIO_MESSAGING_SERVICE_SID={messaging_service_sid}")
    
    print("\n✅ Ahora puedes ejecutar el test de WhatsApp nuevamente:")
    print("   python test_whatsapp.py")
    
except Exception as e:
    print_error(f"Error al verificar configuración: {e}")

print("\n" + "="*80)
