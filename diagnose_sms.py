import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.sms_service import SMSService

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_error(message):
    print(f"   ❌ {message}")

def print_warning(message):
    print(f"   ⚠️  {message}")

def print_info(label, value):
    print(f"   ℹ️  {label}: {value}")

# SIDs de los mensajes enviados
message_sids = [
    'SMba3ff3021373364bf7caaca2a7c843da',  # Nueva Reserva
    'SMdaed3a6c70b4be112301b64142fbfcaf',  # Reserva Aceptada
    'SM5c6963ade49785d968e980a5be44d83f',  # Pago Confirmado
    'SM804acf030088ea854cd4060aca328c45',  # Recordatorio
]

message_names = [
    "Nueva Solicitud de Reserva",
    "Reserva Aceptada",
    "Pago Confirmado",
    "Recordatorio de Servicio"
]

print_header("🔍 VERIFICANDO ESTADO DE LOS MENSAJES EN TWILIO")

for i, (sid, name) in enumerate(zip(message_sids, message_names), 1):
    print(f"\n{i}️⃣ {name}")
    print("-" * 80)
    
    status_info = SMSService.check_message_status(sid)
    
    if 'error' in status_info:
        print_error(f"Error al consultar: {status_info.get('error_message')}")
    else:
        print_info("SID", status_info['sid'])
        print_info("Estado", status_info['status'])
        print_info("Para", status_info['to'])
        print_info("Desde", status_info['from'])
        
        if status_info.get('error_code'):
            print_error(f"Código de error: {status_info['error_code']}")
            print_error(f"Mensaje de error: {status_info['error_message']}")
            
            # Explicar el error
            error_code = status_info['error_code']
            if error_code == 30008:
                print_warning("Error 30008: Unknown error - Problema de entrega")
                print_warning("Posibles causas:")
                print("      • Número destinatario inválido o fuera de servicio")
                print("      • Operadora bloqueó el mensaje")
                print("      • Número no puede recibir SMS")
            elif error_code == 21211:
                print_warning("Error 21211: Número destinatario inválido")
            elif error_code == 21614:
                print_warning("Error 21614: Número no válido para SMS")
            elif error_code == 30007:
                print_warning("Error 30007: Mensaje filtrado por operadora")
        else:
            if status_info['status'] == 'delivered':
                print("   ✅ Mensaje entregado exitosamente")
            elif status_info['status'] == 'sent':
                print("   ⏳ Mensaje enviado, esperando confirmación de entrega")
            elif status_info['status'] == 'queued':
                print("   ⏳ Mensaje en cola")
            elif status_info['status'] in ['failed', 'undelivered']:
                print_error("Mensaje no entregado")

print_header("📊 DIAGNÓSTICO")

print("\n🔍 POSIBLES CAUSAS:")
print("\n1. Número destinatario:")
print("   • Verifica que 0998981436 sea tu número correcto")
print("   • Verifica que pueda recibir SMS")
print("   • Intenta enviar un SMS normal a ese número desde otro teléfono")

print("\n2. Operadora de Ecuador:")
print("   • Algunas operadoras ecuatorianas bloquean SMS internacionales")
print("   • Claro, Movistar, CNT pueden tener filtros")

print("\n3. Twilio:")
print("   • El número +13853344436 es de USA")
print("   • Algunos países requieren números locales para SMS")

print("\n💡 SOLUCIONES:")
print("\n1. Verificar con otro número:")
print("   • ¿Tienes otro número de teléfono para probar?")

print("\n2. Comprar número local de Ecuador en Twilio:")
print("   • Twilio ofrece números de Ecuador (+593)")
print("   • Los SMS desde números locales tienen mejor entrega")

print("\n3. Verificar configuración de operadora:")
print("   • Contacta a tu operadora (Claro/Movistar/CNT)")
print("   • Pregunta si bloquean SMS internacionales")

print("\n" + "="*80)
