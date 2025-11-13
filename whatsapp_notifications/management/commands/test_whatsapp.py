from django.core.management.base import BaseCommand
from whatsapp_notifications.services import WhatsAppService
from whatsapp_notifications.models import WhatsAppLog


class Command(BaseCommand):
    help = 'Prueba el envío de mensajes de WhatsApp'

    def add_arguments(self, parser):
        parser.add_argument(
            'phone_number',
            type=str,
            help='Número de teléfono del destinatario (ej: 593999999999)'
        )
        parser.add_argument(
            'template',
            type=str,
            help='Nombre de la plantilla (booking_created, booking_accepted, payment_confirmed, reminder)'
        )
        parser.add_argument(
            '--var1',
            type=str,
            default='Variable 1',
            help='Primera variable de la plantilla'
        )
        parser.add_argument(
            '--var2',
            type=str,
            default='Variable 2',
            help='Segunda variable de la plantilla'
        )
        parser.add_argument(
            '--var3',
            type=str,
            default='Variable 3',
            help='Tercera variable de la plantilla'
        )

    def handle(self, *args, **options):
        phone = options['phone_number']
        template = options['template']
        
        # Preparar variables según el template
        variables = []
        if template == 'booking_created':
            variables = [
                options.get('var1', 'Juan Pérez'),
                options.get('var2', 'Corte de cabello'),
                options.get('var3', '15/01 14:00')
            ]
        elif template == 'booking_accepted':
            variables = [
                options.get('var1', 'María López'),
                options.get('var2', 'Manicure')
            ]
        elif template == 'payment_confirmed':
            variables = [
                options.get('var1', 'Carlos Ruiz'),
                options.get('var2', 'Limpieza de hogar')
            ]
        elif template == 'reminder':
            variables = [
                options.get('var1', 'Masaje relajante'),
                options.get('var2', '14:30')
            ]
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Plantilla desconocida: {template}')
            )
            self.stdout.write('Plantillas disponibles: booking_created, booking_accepted, payment_confirmed, reminder')
            return
        
        self.stdout.write(f'\n📱 Enviando mensaje de WhatsApp...')
        self.stdout.write(f'📞 Destinatario: {phone}')
        self.stdout.write(f'📝 Plantilla: {template}')
        self.stdout.write(f'📋 Variables: {variables}\n')
        
        # Enviar mensaje
        log = WhatsAppService.send_message(
            recipient_number=phone,
            template_name=template,
            variables=variables
        )
        
        # Mostrar resultado
        if log.status == 'sent':
            self.stdout.write(
                self.style.SUCCESS(f'✅ Mensaje enviado exitosamente')
            )
            self.stdout.write(f'🆔 Message ID: {log.message_id}')
            self.stdout.write(f'📊 Log ID: {log.id}')
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Error al enviar mensaje')
            )
            self.stdout.write(f'🔴 Estado: {log.get_status_display()}')
            if log.error_message:
                self.stdout.write(f'💬 Error: {log.error_message}')
        
        # Mostrar últimos logs
        self.stdout.write('\n📋 Últimos 5 logs de WhatsApp:')
        recent_logs = WhatsAppLog.objects.all()[:5]
        for l in recent_logs:
            status_icon = '✅' if l.status == 'sent' else '❌'
            self.stdout.write(
                f'{status_icon} {l.created_at.strftime("%Y-%m-%d %H:%M:%S")} | '
                f'{l.recipient} | {l.message_type} | {l.get_status_display()}'
            )