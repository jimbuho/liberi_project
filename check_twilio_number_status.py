import os
import django
from twilio.rest import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*70)
print("🔍 VERIFICACIÓN COMPLETA DE CONFIGURACIÓN TWILIO WHATSAPP")
print("="*70)

ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# 1. Verificar cuenta
print("\n1️⃣ INFORMACIÓN DE LA CUENTA")
print("-" * 70)
try:
    account = client.api.accounts(ACCOUNT_SID).fetch()
    print(f"   ✅ Nombre: {account.friendly_name}")
    print(f"   ✅ Estado: {account.status}")
    print(f"   ✅ SID: {account.sid}")
    print(f"   ✅ Tipo: {account.type}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 2. Verificar el número
print("\n2️⃣ VERIFICACIÓN DEL NÚMERO REMITENTE")
print("-" * 70)
print(f"   📱 Número configurado: {FROM_NUMBER}")

# Extraer el número sin 'whatsapp:'
phone_number = FROM_NUMBER.replace('whatsapp:', '')
print(f"   📱 Número limpio: {phone_number}")

# Verificar si es el sandbox
if phone_number == '+14155238886':
    print("\n   🧪 ESTÁS USANDO EL SANDBOX DE TWILIO")
    print("   " + "="*66)
    print("   ⚠️  Este es el número de prueba de Twilio")
    print("   ⚠️  Solo puedes enviar mensajes a números activados")
    print("\n   📋 PASOS PARA ACTIVAR UN NÚMERO EN EL SANDBOX:")
    print("   " + "-"*66)
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   2. Busca tu código de activación (ej: 'join plan-cover')")
    print("   3. Desde WhatsApp, envía ese código al +1 415 523 8886")
    print("   4. Espera la confirmación de Twilio")
    print("   5. Vuelve a ejecutar test_whatsapp_final.py")
    
elif phone_number.startswith('+1555'):
    print("\n   🧪 PARECE SER UN NÚMERO DE SANDBOX PERSONALIZADO")
    print("   " + "="*66)
    print("   ⚠️  Este número puede ser del sandbox de Twilio")
    print("\n   📋 VERIFICA EN LA CONSOLA DE TWILIO:")
    print("   " + "-"*66)
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
    print("   2. Busca tu número: " + phone_number)
    print("   3. Verifica si dice 'Sandbox' o 'Production'")
    print("   4. Si es Sandbox, activa tu número de prueba como se indica arriba")
    
else:
    print("\n   🏢 PARECE SER UN NÚMERO DE PRODUCCIÓN")
    print("   " + "="*66)
    
    # Intentar obtener información del número
    try:
        incoming_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if incoming_numbers:
            number = incoming_numbers[0]
            print(f"   ✅ Número encontrado en tu cuenta")
            print(f"   📋 Nombre: {number.friendly_name}")
            print(f"   📋 SID: {number.sid}")
            print(f"   📋 Capacidades SMS: {number.capabilities.get('sms', False)}")
            print(f"   📋 Capacidades MMS: {number.capabilities.get('mms', False)}")
            print(f"   📋 Capacidades Voice: {number.capabilities.get('voice', False)}")
            
            # Verificar si tiene WhatsApp habilitado
            print("\n   🔍 VERIFICANDO CONFIGURACIÓN DE WHATSAPP...")
            try:
                # Intentar obtener el sender de WhatsApp
                messaging_services = client.messaging.v1.services.list(limit=20)
                
                whatsapp_enabled = False
                for service in messaging_services:
                    print(f"   📋 Servicio encontrado: {service.friendly_name}")
                    
                if not whatsapp_enabled:
                    print("\n   ⚠️  NO SE ENCONTRÓ CONFIGURACIÓN DE WHATSAPP")
                    print("   💡 Este número puede no estar habilitado para WhatsApp")
                    print("\n   📋 PASOS PARA HABILITAR WHATSAPP:")
                    print("   " + "-"*66)
                    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
                    print("   2. Click en 'Request to Enable your Twilio number'")
                    print("   3. Sigue el proceso de verificación con Meta/Facebook")
                    print("   4. Espera la aprobación (1-3 días)")
                    
            except Exception as e:
                print(f"   ℹ️  No se pudo verificar servicios de mensajería: {e}")
        else:
            print("   ⚠️  Número NO encontrado en tu cuenta de Twilio")
            print("   💡 Puede ser un número de Sandbox o no estar registrado")
            
    except Exception as e:
        print(f"   ℹ️  No se pudo verificar el número: {e}")

# 3. Verificar templates
print("\n3️⃣ VERIFICACIÓN DE TEMPLATES")
print("-" * 70)

TEMPLATES = settings.TWILIO_TEMPLATES

for template_name, template_info in TEMPLATES.items():
    content_sid = template_info['content_sid']
    print(f"\n   📋 Template: {template_name}")
    print(f"   🆔 Content SID: {content_sid}")
    
    try:
        content = client.content.v1.contents(content_sid).fetch()
        print(f"   ✅ Nombre: {content.friendly_name}")
        print(f"   ✅ Idioma: {content.language}")
        print(f"   ✅ Tipos: {content.types}")
        
        # Intentar obtener el estado de aprobación
        # Nota: La API de Twilio puede no exponer approval_status directamente
        # Necesitarías verificar esto manualmente en la consola
        print(f"   ℹ️  Verifica el estado de aprobación en:")
        print(f"      https://console.twilio.com/us1/develop/sms/content-editor")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

# 4. Configuración general
print("\n4️⃣ CONFIGURACIÓN GENERAL")
print("-" * 70)
print(f"   🧪 Modo de prueba: {'ACTIVADO ✅' if settings.WHATSAPP_TEST_MODE else 'DESACTIVADO ❌'}")
print(f"   📊 Templates configurados: {len(TEMPLATES)}")
print(f"   🔑 Account SID: {ACCOUNT_SID[:10]}...{ACCOUNT_SID[-4:]}")
print(f"   🔐 Auth Token: {'*' * 20}{AUTH_TOKEN[-4:]}")

# 5. Recomendaciones
print("\n5️⃣ RECOMENDACIONES")
print("-" * 70)

if phone_number in ['+14155238886', '+15558557677']:
    print("   🎯 ACCIÓN REQUERIDA: Activar número en Sandbox")
    print("   " + "="*66)
    print("   1. Abre WhatsApp en tu teléfono (+593998981436)")
    print("   2. Envía un mensaje a: +1 415 523 8886")
    print("   3. Mensaje: 'join [tu-codigo-sandbox]'")
    print("   4. Espera confirmación")
    print("   5. Ejecuta: python test_whatsapp_final.py")
    print("\n   💡 Encuentra tu código en:")
    print("      https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
else:
    print("   🎯 ACCIÓN REQUERIDA: Verificar estado de WhatsApp Business")
    print("   " + "="*66)
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
    print("   2. Verifica que tu número esté en estado 'Active'")
    print("   3. Verifica que los templates estén 'Approved'")
    print("   4. Si no está activo, inicia el proceso de verificación")

print("\n" + "="*70)
print("✅ Verificación completada")
print("="*70)
print("\n💡 Próximo paso: Revisa SOLUCION_ERROR_63051.md para instrucciones detalladas")
print()
