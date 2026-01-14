"""
Script automatizado para migrar TODOS los emails hardcodeados a templates
"""
import re
import os
from pathlib import Path

# Crear directorio de templates si no existe
templates_dir = Path('templates/emails')
templates_dir.mkdir(parents=True, exist_ok=True)

# Leer tasks.py
with open('apps/core/tasks.py', 'r', encoding='utf-8') as f:
    tasks_content = f.read()

# Definir todos los tasks que necesitan templates
tasks_to_migrate = [
    {
        'name': 'send_provider_approval_notification_task',
        'template': 'provider_approval_notification',
        'subject': 'Nueva Solicitud de Aprobación de Proveedor',
        'recipient': 'admin'
    },
    {
        'name': 'send_provider_approval_confirmed_task',
        'template': 'provider_approval_confirmed',
        'subject': 'Tu Perfil Ha Sido Aprobado',
        'recipient': 'provider'
    },
    {
        'name': 'send_provider_rejection_notification_task',
        'template': 'provider_rejection',
        'subject': 'Actualización sobre tu perfil de proveedor',
        'recipient': 'provider'
    },
    {
        'name': 'send_new_booking_to_provider_task',
        'template': 'new_booking_to_provider',
        'subject': 'Nueva Reserva',
        'recipient': 'provider'
    },
    {
        'name': 'send_payment_approved_to_customer_task',
        'template': 'payment_approved_customer',
        'subject': 'Pago Aprobado',
        'recipient': 'customer'
    },
    {
        'name': 'send_payment_approved_to_provider_task',
        'template': 'payment_approved_provider',
        'subject': 'Pago Confirmado',
        'recipient': 'provider'
    },
    {
        'name': 'send_payment_proof_received_task',
        'template': 'payment_proof_received',
        'subject': 'Comprobante de Pago Recibido',
        'recipient': 'customer'
    },
    {
        'name': 'send_withdrawal_request_to_admins_task',
        'template': 'withdrawal_request_admin',
        'subject': 'Nueva Solicitud de Retiro',
        'recipient': 'admin'
    },
    {
        'name': 'send_withdrawal_completed_to_provider_task',
        'template': 'withdrawal_completed',
        'subject': 'Retiro Completado',
        'recipient': 'provider'
    },
    {
        'name': 'send_payment_confirmed_to_customer_task',
        'template': 'payment_confirmed_customer',
        'subject': 'Pago Confirmado',
        'recipient': 'customer'
    },
    {
        'name': 'send_payment_received_to_provider_task',
        'template': 'payment_received_provider',
        'subject': 'Pago Recibido',
        'recipient': 'provider'
    },
    {
        'name': 'send_provider_completion_reminder_email_task',
        'template': 'provider_completion_reminder',
        'subject': 'Recordatorio: Completa tu servicio',
        'recipient': 'provider'
    },
    {
        'name': 'send_service_completion_check_email_task',
        'template': 'service_completion_check',
        'subject': '¿Recibiste tu servicio?',
        'recipient': 'customer'
    },
    {
        'name': 'send_incident_notification_to_admins_task',
        'template': 'incident_notification_admin',
        'subject': 'Incidencia Reportada',
        'recipient': 'admin'
    },
    {
        'name': 'send_password_reset_email_task',
        'template': 'password_reset',
        'subject': 'Restablecer tu contraseña',
        'recipient': 'user'
    },
    {
        'name': 'send_validation_result_to_admin_task',
        'template': 'validation_result_admin',
        'subject': 'Resultado de Validación de Proveedor',
        'recipient': 'admin'
    },
]

print(f"Total de tasks a migrar: {len(tasks_to_migrate)}")
print("="*80)

# Extraer el contenido de cada mensaje
for task in tasks_to_migrate:
    # Buscar la función
    pattern = rf'def {task["name"]}\([^)]*\):.*?(?=\n@shared_task|\ndef |\Z)'
    match = re.search(pattern, tasks_content, re.DOTALL)
    
    if match:
        function_content = match.group(0)
        
        # Buscar el mensaje hardcodeado
        message_pattern = r'message = f"""(.*?)"""'
        message_match = re.search(message_pattern, function_content, re.DOTALL)
        
        if message_match:
            message_content = message_match.group(1).strip()
            print(f"\n✅ {task['name']}")
            print(f"   Template: {task['template']}")
            print(f"   Longitud: {len(message_content)} caracteres")
            
            # Guardar el contenido para crear templates
            task['message_content'] = message_content
        else:
            print(f"\n⚠️  {task['name']} - No se encontró mensaje")
    else:
        print(f"\n❌ {task['name']} - No se encontró función")

print("\n" + "="*80)
print(f"Mensajes extraídos: {sum(1 for t in tasks_to_migrate if 'message_content' in t)}")
print("\nPróximo paso: Generar templates HTML y TXT")
