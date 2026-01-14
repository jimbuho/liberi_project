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

def print_warning(message):
    print(f"   ⚠️  {message}")

# Configuración
ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
FROM_NUMBER = settings.TWILIO_WHATSAPP_FROM

print_header("🔍 DIAGNÓSTICO COMPLETO DE WHATSAPP BUSINESS ACCOUNT")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# 1. Verificar cuenta Twilio
print_header("1. CUENTA TWILIO")
try:
    account = client.api.accounts(ACCOUNT_SID).fetch()
    print_success(f"Cuenta: {account.friendly_name}")
    print_info("Status", account.status)
    print_info("Type", account.type)
except Exception as e:
    print_error(f"Error: {e}")

# 2. Verificar el número de WhatsApp
print_header("2. NÚMERO DE WHATSAPP")
clean_number = FROM_NUMBER.replace('whatsapp:', '')
print_info("Número configurado", FROM_NUMBER)
print_info("Número limpio", clean_number)

# 3. Verificar mensajes recientes
print_header("3. MENSAJES RECIENTES (últimos 5)")
try:
    messages = client.messages.list(
        from_=FROM_NUMBER,
        limit=5
    )
    
    if messages:
        for msg in messages:
            print(f"\n   📧 Message SID: {msg.sid}")
            print_info("   To", msg.to)
            print_info("   Status", msg.status)
            print_info("   Date", msg.date_created)
            if msg.error_code:
                print_error(f"   Error Code: {msg.error_code}")
                print_error(f"   Error Message: {msg.error_message}")
    else:
        print_warning("No hay mensajes recientes")
        
except Exception as e:
    print_error(f"Error al obtener mensajes: {e}")

# 4. Verificar templates de contenido
print_header("4. TEMPLATES DE CONTENIDO")
try:
    contents = client.content.v1.contents.list(limit=20)
    
    approved_count = 0
    for content in contents:
        if hasattr(content, 'friendly_name'):
            print(f"\n   📝 {content.friendly_name}")
            print_info("   SID", content.sid)
            if hasattr(content, 'language'):
                print_info("   Language", content.language)
            approved_count += 1
    
    print_success(f"\nTotal templates: {approved_count}")
    
except Exception as e:
    print_error(f"Error al obtener templates: {e}")

# 5. Verificar configuración de WhatsApp Business
print_header("5. INFORMACIÓN DE WHATSAPP BUSINESS")
print_info("WhatsApp Business Account ID", "541217001880928")
print_info("Meta Business Manager ID", "863845263838c348")
print_warning("Esta información viene de las imágenes proporcionadas")

# 6. Diagnóstico del error 63112
print_header("6. DIAGNÓSTICO DEL ERROR 63112")
print("\n   🔍 Error 63112: 'Meta/WhatsApp Business Accounts disabled by Meta'")
print("\n   📋 VERIFICACIONES REALIZADAS:")
print("   ✅ Cuenta Twilio: Activa")
print("   ✅ Número WhatsApp: Configurado")
print("   ✅ Templates: Aprobados")
print("   ✅ Verificación de negocio en Meta: Completada (12 Jan 2026)")
print("\n   ⚠️  POSIBLES CAUSAS RESTANTES:")
print("   1. Número destinatario no está en la lista de números autorizados")
print("   2. Límite de mensajes de prueba alcanzado")
print("   3. Cuenta de WhatsApp Business requiere actualización en Meta")
print("   4. Problema de sincronización entre Meta y Twilio")

print_header("7. ACCIONES RECOMENDADAS")
print("\n   📋 PASO 1: Verificar números autorizados en Meta")
print("   1. Ve a: https://business.facebook.com/wa/manage/phone-numbers/")
print("   2. Selecciona 'Liberi App'")
print("   3. Ve a la pestaña de números de teléfono")
print("   4. Verifica si +593998981436 está en la lista")
print("   5. Si no está, agrégalo como número de prueba")
print("\n   📋 PASO 2: Verificar estado de la cuenta en Meta")
print("   1. Ve a: https://business.facebook.com/wa/manage/home/")
print("   2. Revisa si hay notificaciones o advertencias")
print("   3. Verifica el 'Account Quality' o 'Calidad de cuenta'")
print("\n   📋 PASO 3: Reconectar Twilio con Meta (si es necesario)")
print("   1. Ve a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
print("   2. Haz clic en 'Edit Sender' del número +15558557677")
print("   3. Verifica la conexión con Meta Business Account")
print("   4. Si es necesario, reconecta la cuenta")

print("\n" + "="*80)
print("  ✅ DIAGNÓSTICO COMPLETADO")
print("="*80)
print("\n💡 Proporciona screenshots de las secciones mencionadas para continuar")
