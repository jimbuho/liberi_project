import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.sms_service import SMSService

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_success(message):
    print(f"   ✅ {message}")

def print_info(label, value):
    print(f"   ℹ️  {label}: {value}")

# Tu número
RECIPIENT = '0998981436'

print_header("📱 ENVIANDO 4 EJEMPLOS DE SMS A 0998981436")

print("\n⏳ Enviando mensajes...")
print("   (Espera unos segundos entre cada uno)")

import time

# 1. Nueva Reserva
print("\n1️⃣ Enviando: NUEVA RESERVA...")
log1 = SMSService.send_booking_created(
    recipient_number=RECIPIENT,
    client_name="Juan Pérez",
    service_name="Limpieza Profunda",
    datetime_str="15/01/2026 14:00"
)
print_success(f"Enviado - SID: {log1.message_id}")
time.sleep(3)

# 2. Reserva Aceptada
print("\n2️⃣ Enviando: RESERVA ACEPTADA...")
log2 = SMSService.send_booking_accepted(
    recipient_number=RECIPIENT,
    provider_name="María García",
    service_name="Corte de Cabello",
    booking_id="abc123"
)
print_success(f"Enviado - SID: {log2.message_id}")
time.sleep(3)

# 3. Pago Confirmado
print("\n3️⃣ Enviando: PAGO CONFIRMADO...")
log3 = SMSService.send_payment_confirmed(
    recipient_number=RECIPIENT,
    client_name="Pedro López",
    service_name="Manicure"
)
print_success(f"Enviado - SID: {log3.message_id}")
time.sleep(3)

# 4. Recordatorio
print("\n4️⃣ Enviando: RECORDATORIO DE SERVICIO...")
log4 = SMSService.send_service_reminder(
    recipient_number=RECIPIENT,
    service_name="Limpieza de Oficina",
    time_str="16:00",
    booking_id="xyz789"
)
print_success(f"Enviado - SID: {log4.message_id}")

print_header("✅ TODOS LOS MENSAJES ENVIADOS")
print("\n📱 Revisa tu teléfono 0998981436")
print("   Deberías recibir 4 SMS en los próximos segundos:")
print("\n   1️⃣ Nueva Solicitud de Reserva")
print("   2️⃣ Reserva Aceptada")
print("   3️⃣ Pago Confirmado")
print("   4️⃣ Recordatorio de Servicio")
print("\n" + "="*80)
