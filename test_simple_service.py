import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.simple_service import WhatsAppSimpleService
import time

print("="*70)
print("🔍 TEST DE WHATSAPP - SERVICIO SIMPLE")
print("="*70)

print("\n📱 Probando los 4 tipos de notificaciones:\n")

# 1. Nueva reserva
print("1️⃣ Enviando notificación de nueva reserva...")
log1 = WhatsAppSimpleService.send_booking_created(
    recipient_number='0998981436',
    customer_name='Diego González',
    service='Limpieza Profunda',
    datetime='15/01/2026 09:00'
)
print(f"   {'✅' if log1.status == 'sent' else '❌'} Status: {log1.status}")
if log1.message_id != 'TEST_MODE':
    print(f"   🆔 SID: {log1.message_id}")
time.sleep(2)

# 2. Reserva aceptada
print("\n2️⃣ Enviando notificación de reserva aceptada...")
log2 = WhatsAppSimpleService.send_booking_accepted(
    recipient_number='0998981436',
    provider_name='María García',
    service='Limpieza Profunda'
)
print(f"   {'✅' if log2.status == 'sent' else '❌'} Status: {log2.status}")
if log2.message_id != 'TEST_MODE':
    print(f"   🆔 SID: {log2.message_id}")
time.sleep(2)

# 3. Pago confirmado
print("\n3️⃣ Enviando notificación de pago confirmado...")
log3 = WhatsAppSimpleService.send_payment_confirmed(
    recipient_number='0998981436',
    customer_name='Diego González',
    service='Limpieza Profunda'
)
print(f"   {'✅' if log3.status == 'sent' else '❌'} Status: {log3.status}")
if log3.message_id != 'TEST_MODE':
    print(f"   🆔 SID: {log3.message_id}")
time.sleep(2)

# 4. Recordatorio
print("\n4️⃣ Enviando recordatorio...")
log4 = WhatsAppSimpleService.send_reminder(
    recipient_number='0998981436',
    service='Limpieza Profunda',
    time='09:00'
)
print(f"   {'✅' if log4.status == 'sent' else '❌'} Status: {log4.status}")
if log4.message_id != 'TEST_MODE':
    print(f"   🆔 SID: {log4.message_id}")

print("\n" + "="*70)
print("✅ Test completado")
print("="*70)

# Resumen
total = 4
sent = sum(1 for log in [log1, log2, log3, log4] if log.status == 'sent')
failed = total - sent

print(f"\n📊 Resumen:")
print(f"   Total: {total} mensajes")
print(f"   Enviados: {sent} ✅")
print(f"   Fallidos: {failed} ❌")

if sent == total:
    print(f"\n🎉 ¡Todos los mensajes fueron enviados exitosamente!")
    print(f"   Revisa tu WhatsApp para verlos")
else:
    print(f"\n⚠️  Algunos mensajes fallaron")
    print(f"   Revisa los logs para más detalles")

print("\n💡 NOTA:")
print("   Este servicio usa mensajes simples (sin templates)")
print("   Funciona en Sandbox pero no en producción")
print("   Para producción, necesitas templates aprobados por Meta")
print()
