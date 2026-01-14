import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.sms_service import SMSService
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

print_header("🧪 TEST COMPLETO DEL SERVICIO SMS")

# 1. Validar configuración
print_header("1. VALIDACIÓN DE CONFIGURACIÓN")
validation = SMSService.validate_configuration()

if validation['valid']:
    print_success("Configuración válida")
else:
    print_error("Configuración inválida")
    for error in validation['errors']:
        print_error(f"  • {error}")

if validation['warnings']:
    for warning in validation['warnings']:
        print(f"   ⚠️  {warning}")

print_info("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID[:10] + "...")
print_info("TWILIO_SMS_FROM", settings.TWILIO_SMS_FROM)
print_info("USE_SMS_NOTIFICATIONS", settings.USE_SMS_NOTIFICATIONS)

# 2. Probar formateo de números
print_header("2. TEST DE FORMATEO DE NÚMEROS")

test_numbers = [
    '0998981436',
    '593998981436',
    '+593998981436',
    '0958840107',
]

for number in test_numbers:
    formatted = SMSService.format_phone_number(number)
    print_info(f"{number:20s} →", formatted)

# 3. Enviar mensajes de prueba
print_header("3. ENVÍO DE MENSAJES DE PRUEBA")

# Tus números
recipients = ['+593998981436', '+593958840107']

print("\n📱 Test 1: Notificación de nueva reserva")
print("-" * 80)
log1 = SMSService.send_booking_created(
    recipient_number=recipients[0],
    client_name="Juan Pérez",
    service_name="Limpieza Profunda",
    datetime_str="15/01/2026 14:00"
)
print_info("Status", log1.status)
print_info("Message SID", log1.message_id or "N/A")
if log1.error_message:
    print_error(f"Error: {log1.error_message}")

print("\n📱 Test 2: Notificación de reserva aceptada")
print("-" * 80)
log2 = SMSService.send_booking_accepted(
    recipient_number=recipients[1],
    provider_name="María García",
    service_name="Corte de Cabello",
    booking_id="abc123"
)
print_info("Status", log2.status)
print_info("Message SID", log2.message_id or "N/A")
if log2.error_message:
    print_error(f"Error: {log2.error_message}")

print("\n📱 Test 3: Notificación de pago confirmado")
print("-" * 80)
log3 = SMSService.send_payment_confirmed(
    recipient_number=recipients[0],
    client_name="Pedro López",
    service_name="Manicure"
)
print_info("Status", log3.status)
print_info("Message SID", log3.message_id or "N/A")
if log3.error_message:
    print_error(f"Error: {log3.error_message}")

print("\n📱 Test 4: Recordatorio de servicio")
print("-" * 80)
log4 = SMSService.send_service_reminder(
    recipient_number=recipients[1],
    service_name="Limpieza de Oficina",
    time_str="16:00",
    booking_id="xyz789"
)
print_info("Status", log4.status)
print_info("Message SID", log4.message_id or "N/A")
if log4.error_message:
    print_error(f"Error: {log4.error_message}")

# 4. Verificar estados
print_header("4. VERIFICACIÓN DE ESTADOS (esperando 5 segundos...)")
import time
time.sleep(5)

all_logs = [log1, log2, log3, log4]
for i, log in enumerate(all_logs, 1):
    if log.message_id:
        status_info = SMSService.check_message_status(log.message_id)
        if 'error' not in status_info:
            print(f"\n   Mensaje {i}:")
            print_info("  SID", status_info['sid'])
            print_info("  Status", status_info['status'])
            if status_info.get('error_code'):
                print_error(f"  Error: {status_info['error_code']} - {status_info['error_message']}")

# 5. Resumen
print_header("📊 RESUMEN")

successful = sum(1 for log in all_logs if log.status == 'sent')
failed = sum(1 for log in all_logs if log.status == 'failed')

print(f"\n   Total mensajes: {len(all_logs)}")
print(f"   ✅ Exitosos: {successful}")
print(f"   ❌ Fallidos: {failed}")

if successful == len(all_logs):
    print("\n" + "="*80)
    print("  🎉 ¡TODOS LOS MENSAJES ENVIADOS EXITOSAMENTE!")
    print("="*80)
    print("\n   ✅ El servicio SMS está funcionando correctamente")
    print("   ✅ Revisa tus teléfonos para ver los mensajes")
    print("\n   📋 PRÓXIMOS PASOS:")
    print("   1. Actualizar el código de bookings para usar SMS")
    print("   2. Configurar las variables de entorno en producción")
    print("   3. Desplegar los cambios")
else:
    print("\n   ⚠️  Algunos mensajes fallaron")
    print("   Revisa los logs arriba para más detalles")

print("\n" + "="*80)
print("  ✅ TEST COMPLETADO")
print("="*80)
