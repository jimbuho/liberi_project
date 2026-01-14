"""
Script para diagnosticar problemas con WhatsApp Business en Twilio.
Verifica el estado del número, límites de mensajería y configuración.
"""
import os
import django
from twilio.rest import Client
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*80)
print("🔍 DIAGNÓSTICO COMPLETO DE WHATSAPP BUSINESS")
print("="*80)

ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
WHATSAPP_NUMBER = '+15558557677'  # El número de Facebook/Meta

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# 1. Verificar estado de la cuenta
print("\n1️⃣ ESTADO DE LA CUENTA TWILIO")
print("-"*80)
try:
    account = client.api.accounts(ACCOUNT_SID).fetch()
    print(f"   ✅ Nombre: {account.friendly_name}")
    print(f"   ✅ Estado: {account.status}")
    print(f"   ✅ Tipo: {account.type}")
    
    # Verificar balance (si está disponible)
    try:
        balance = client.balance.fetch()
        print(f"   💰 Balance: {balance.balance} {balance.currency}")
    except:
        print(f"   ℹ️  Balance: No disponible en esta API")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# 2. Verificar mensajes recientes
print("\n2️⃣ MENSAJES RECIENTES (Últimas 24 horas)")
print("-"*80)
try:
    # Obtener mensajes de las últimas 24 horas
    yesterday = datetime.now() - timedelta(days=1)
    
    messages = client.messages.list(
        from_=f'whatsapp:{WHATSAPP_NUMBER}',
        date_sent_after=yesterday,
        limit=50
    )
    
    if not messages:
        print("   ℹ️  No hay mensajes enviados en las últimas 24 horas")
    else:
        print(f"   📊 Total de mensajes: {len(messages)}")
        
        # Contar por estado
        status_count = {}
        error_count = {}
        
        for msg in messages:
            status = msg.status
            status_count[status] = status_count.get(status, 0) + 1
            
            if msg.error_code:
                error_count[msg.error_code] = error_count.get(msg.error_code, 0) + 1
        
        print("\n   📈 Mensajes por estado:")
        for status, count in status_count.items():
            icon = "✅" if status == "delivered" else "⏳" if status == "sent" else "❌"
            print(f"      {icon} {status}: {count}")
        
        if error_count:
            print("\n   ⚠️  Errores encontrados:")
            for error_code, count in error_count.items():
                print(f"      🔴 Error {error_code}: {count} mensajes")
                
                # Explicar errores comunes
                error_explanations = {
                    63051: "Número destinatario no puede recibir mensajes (no registrado o bloqueado)",
                    63027: "Template no aprobado o variables incorrectas",
                    63007: "Número remitente no configurado correctamente",
                    21408: "Número bloqueado o no acepta mensajes",
                }
                
                if error_code in error_explanations:
                    print(f"         💡 {error_explanations[error_code]}")
        
        # Mostrar últimos 5 mensajes
        print("\n   📝 Últimos 5 mensajes:")
        for i, msg in enumerate(messages[:5], 1):
            status_icon = "✅" if msg.status == "delivered" else "❌" if msg.status in ["failed", "undelivered"] else "⏳"
            print(f"\n      {i}. {status_icon} {msg.sid}")
            print(f"         Para: {msg.to}")
            print(f"         Estado: {msg.status}")
            print(f"         Fecha: {msg.date_sent}")
            if msg.error_code:
                print(f"         ❌ Error {msg.error_code}: {msg.error_message}")
                
except Exception as e:
    print(f"   ❌ Error al obtener mensajes: {e}")

# 3. Verificar configuración de WhatsApp Senders
print("\n3️⃣ CONFIGURACIÓN DE WHATSAPP SENDERS")
print("-"*80)
print("   ℹ️  Para verificar el estado completo del número:")
print("   🔗 https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
print("\n   Verifica:")
print("   • Estado del número: Debe ser 'Active' o 'Connected'")
print("   • Quality Rating: Debe ser 'Green' o 'Yellow' (no 'Red')")
print("   • Messaging Limit: Verifica que no hayas alcanzado el límite")
print("   • Status: Debe ser 'Connected'")

# 4. Verificar templates
print("\n4️⃣ TEMPLATES CONFIGURADOS")
print("-"*80)

TEMPLATES = settings.TWILIO_TEMPLATES
templates_ok = 0
templates_error = 0

for template_name, template_info in TEMPLATES.items():
    content_sid = template_info['content_sid']
    
    try:
        content = client.content.v1.contents(content_sid).fetch()
        print(f"\n   ✅ {template_name}")
        print(f"      SID: {content_sid}")
        print(f"      Nombre: {content.friendly_name}")
        print(f"      Idioma: {content.language}")
        templates_ok += 1
        
    except Exception as e:
        print(f"\n   ❌ {template_name}")
        print(f"      Error: {e}")
        templates_error += 1

print(f"\n   📊 Resumen: {templates_ok} OK, {templates_error} con errores")

# 5. Verificar número en incoming_phone_numbers
print("\n5️⃣ NÚMEROS REGISTRADOS EN TWILIO")
print("-"*80)

try:
    incoming_numbers = client.incoming_phone_numbers.list(limit=50)
    
    whatsapp_number_found = False
    for number in incoming_numbers:
        if WHATSAPP_NUMBER in number.phone_number:
            whatsapp_number_found = True
            print(f"\n   ✅ Número encontrado: {number.phone_number}")
            print(f"      Nombre: {number.friendly_name}")
            print(f"      SID: {number.sid}")
            print(f"      Capacidades:")
            print(f"         SMS: {number.capabilities.get('sms', False)}")
            print(f"         MMS: {number.capabilities.get('mms', False)}")
            print(f"         Voice: {number.capabilities.get('voice', False)}")
            
            # Verificar webhooks configurados
            if number.sms_url:
                print(f"      SMS URL: {number.sms_url}")
            if number.status_callback:
                print(f"      Status Callback: {number.status_callback}")
    
    if not whatsapp_number_found:
        print(f"\n   ⚠️  El número {WHATSAPP_NUMBER} NO está en incoming_phone_numbers")
        print(f"      Esto es normal para números de WhatsApp Business")
        print(f"      El número está gestionado por Meta/Facebook, no directamente por Twilio")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# 6. Resumen y recomendaciones
print("\n" + "="*80)
print("📊 RESUMEN Y DIAGNÓSTICO")
print("="*80)

print("\n🔍 POSIBLES CAUSAS DEL ERROR 63051:")
print("-"*80)

print("\n1. **Límite de mensajería alcanzado**")
print("   • WhatsApp Business tiene límites diarios de mensajes")
print("   • Verifica en: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
print("   • Busca 'Messaging Limit' o 'Tier'")

print("\n2. **Calificación de calidad baja**")
print("   • Si muchos usuarios bloquean o reportan tus mensajes, Meta limita tu cuenta")
print("   • Verifica 'Quality Rating' en la consola")
print("   • Debe ser 'Green' o 'Yellow', no 'Red'")

print("\n3. **Número desconectado o suspendido**")
print("   • Verifica en Facebook Business Manager")
print("   • El número debe estar 'Conectado' y 'Activo'")

print("\n4. **Cambio en la configuración de Meta**")
print("   • Meta puede haber cambiado políticas o requerimientos")
print("   • Verifica notificaciones en Facebook Business Manager")

print("\n5. **Problema con el número destinatario**")
print("   • El número +593998981436 puede estar bloqueado")
print("   • O no tener WhatsApp instalado")
print("   • Prueba con otro número para descartar")

print("\n" + "="*80)
print("🎯 PRÓXIMOS PASOS RECOMENDADOS")
print("="*80)

print("\n1. **Verifica en Twilio Console** (MÁS IMPORTANTE)")
print("   🔗 https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders")
print("   Busca tu número y verifica:")
print("   • Status: Connected")
print("   • Quality Rating: Green/Yellow")
print("   • Messaging Limit: No alcanzado")

print("\n2. **Verifica en Facebook Business Manager**")
print("   🔗 https://business.facebook.com/")
print("   • Ve a WhatsApp Accounts")
print("   • Verifica que el número esté activo")
print("   • Revisa notificaciones o alertas")

print("\n3. **Prueba con otro número destinatario**")
print("   • Usa un número diferente para descartar problemas con el destinatario")
print("   • python test_business_number.py (edita el RECIPIENT)")

print("\n4. **Revisa logs de Twilio**")
print("   🔗 https://console.twilio.com/us1/monitor/logs/sms")
print("   • Busca mensajes recientes")
print("   • Verifica errores detallados")

print("\n5. **Contacta a soporte de Twilio**")
print("   • Si todo parece correcto pero sigue fallando")
print("   • Puede haber un problema en el backend de Twilio/Meta")

print("\n" + "="*80)
