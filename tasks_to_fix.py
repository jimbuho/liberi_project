"""
Script para identificar todos los tasks que necesitan templates
"""

tasks_info = [
    {
        'line': 137,
        'function': 'send_provider_approval_notification_task',
        'template_name': 'provider_approval_notification',
        'subject': 'Nueva Solicitud de Aprobación de Proveedor'
    },
    {
        'line': 180,
        'function': 'send_provider_approval_confirmed_task',
        'template_name': 'provider_approval_confirmed',
        'subject': 'Tu Perfil Ha Sido Aprobado'
    },
    {
        'line': 226,
        'function': 'send_provider_rejection_notification_task',
        'template_name': 'provider_rejection',
        'subject': 'Actualización sobre tu perfil de proveedor'
    },
    {
        'line': 271,
        'function': 'send_new_booking_to_provider_task',
        'template_name': 'new_booking_to_provider',
        'subject': 'Nueva Reserva'
    },
    {
        'line': 380,
        'function': 'send_payment_approved_to_customer_task',
        'template_name': 'payment_approved_customer',
        'subject': 'Pago Aprobado'
    },
    {
        'line': 431,
        'function': 'send_payment_approved_to_provider_task',
        'template_name': 'payment_approved_provider',
        'subject': 'Pago Confirmado'
    },
    {
        'line': 482,
        'function': 'send_payment_proof_received_task',
        'template_name': 'payment_proof_received',
        'subject': 'Comprobante de Pago Recibido'
    },
    {
        'line': 534,
        'function': 'send_withdrawal_request_to_admins_task',
        'template_name': 'withdrawal_request_admin',
        'subject': 'Nueva Solicitud de Retiro'
    },
    {
        'line': 577,
        'function': 'send_withdrawal_completed_to_provider_task',
        'template_name': 'withdrawal_completed',
        'subject': 'Retiro Completado'
    },
    {
        'line': 626,
        'function': 'send_payment_confirmed_to_customer_task',
        'template_name': 'payment_confirmed_customer',
        'subject': 'Pago Confirmado'
    },
    {
        'line': 665,
        'function': 'send_payment_received_to_provider_task',
        'template_name': 'payment_received_provider',
        'subject': 'Pago Recibido'
    },
    {
        'line': 857,
        'function': 'send_provider_completion_reminder_email_task',
        'template_name': 'provider_completion_reminder',
        'subject': 'Recordatorio: Completa tu servicio'
    },
    {
        'line': 916,
        'function': 'send_service_completion_check_email_task',
        'template_name': 'service_completion_check',
        'subject': '¿Recibiste tu servicio?'
    },
    {
        'line': 971,
        'function': 'send_incident_notification_to_admins_task',
        'template_name': 'incident_notification_admin',
        'subject': 'Incidencia Reportada'
    },
    {
        'line': 1037,
        'function': 'send_password_reset_email_task',
        'template_name': 'password_reset',
        'subject': 'Restablecer tu contraseña'
    },
    {
        'line': 1227,
        'function': 'send_validation_result_to_admin_task',
        'template_name': 'validation_result_admin',
        'subject': 'Resultado de Validación de Proveedor'
    },
]

print("Tasks que necesitan templates:")
print("="*80)
for task in tasks_info:
    print(f"\n{task['function']}")
    print(f"  Línea: {task['line']}")
    print(f"  Template: {task['template_name']}")
    print(f"  Subject: {task['subject']}")
