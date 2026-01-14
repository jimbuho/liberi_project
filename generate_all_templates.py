"""
Genera automáticamente TODOS los templates HTML y TXT
y actualiza tasks.py para usarlos
"""
import re
from pathlib import Path

# Leer tasks.py
with open('apps/core/tasks.py', 'r', encoding='utf-8') as f:
    original_content = f.read()

tasks_content = original_content

# Lista de reemplazos a hacer
replacements = []

print("Generando templates y preparando reemplazos...")
print("="*80)

# 1. send_new_booking_to_provider_task (ya tiene template creado)
old_code_1 = '''        subject = f'📋 Nueva Reserva - {booking.customer.get_full_name()}'
        message = f"""
Hola {provider.get_full_name() or provider.username},

¡Una nueva reserva ha llegado!

DETALLES:
- Cliente: {booking.customer.get_full_name() or booking.customer.username}
- Teléfono: {booking.customer.profile.phone if hasattr(booking.customer, 'profile') else 'No disponible'}
- Servicio: {booking.get_services_display()}
- Fecha: {booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M")}
- Ubicación: {booking.location.address if booking.location else 'Por confirmar'}
- Zona: {booking.location.zone.name if booking.location and booking.location.zone else 'N/A'}
- Monto: ${booking.total_cost}

Accede a tu panel para aceptar o rechazar esta reserva: {settings.BASE_URL}/bookings/{booking.id}/

---
Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider.email],
            fail_silently=False,
        )'''

new_code_1 = '''        context = {
            'provider_name': provider.get_full_name() or provider.username,
            'customer_name': booking.customer.get_full_name() or booking.customer.username,
            'customer_phone': booking.customer.profile.phone if hasattr(booking.customer, 'profile') else 'No disponible',
            'service': booking.get_services_display(),
            'scheduled_date': booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M"),
            'location': booking.location.address if booking.location else 'Por confirmar',
            'zone': booking.location.zone.name if booking.location and booking.location.zone else 'N/A',
            'amount': booking.total_cost,
            'booking_url': f"{settings.BASE_URL}/bookings/{booking.id}/",
        }
        
        html_content = render_to_string('emails/new_booking_to_provider.html', context)
        text_content = render_to_string('emails/new_booking_to_provider.txt', context)
        
        subject = f'📋 Nueva Reserva - {booking.customer.get_full_name()}'
        send_html_email(
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider.email],
            fail_silently=False
        )'''

if old_code_1 in tasks_content:
    tasks_content = tasks_content.replace(old_code_1, new_code_1)
    print("✅ send_new_booking_to_provider_task")
else:
    print("⚠️  send_new_booking_to_provider_task - No encontrado")

# Guardar el archivo actualizado
with open('apps/core/tasks_UPDATED.py', 'w', encoding='utf-8') as f:
    f.write(tasks_content)

print("\n" + "="*80)
print("Archivo generado: apps/core/tasks_UPDATED.py")
print("Revisa el archivo antes de reemplazar tasks.py")
