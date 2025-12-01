from django.core.management.base import BaseCommand
from django.conf import settings
from apps.whatsapp_notifications.services import WhatsAppService
from apps.whatsapp_notifications.models import WhatsAppLog


class Command(BaseCommand):
    help = 'Prueba el envío de mensajes de WhatsApp via Twilio'

    def add_arguments(self, parser):
        parser.add_argument(
            'phone_number',
            type=str,
            help='Número de teléfono del destinatario (ej: 593999999999 o 0999999999)'
        )
        parser.add_argument(
            '--template',
            type=str,
            default=None,
            help='Nombre de la plantilla (booking_created, booking_accepted, payment_confirmed, reminder)'
        )
        parser.add_argument(
            '--message',
            type=str,
            default=None,
            help='Mensaje simple (solo para sandbox de Twilio)'
        )
        parser.add_argument(
            '--var1',
            type=str,
            default='Juan Pérez',
            help='Primera variable de la plantilla'
        )
        parser.add_argument(
            '--var2',
            type=str,
            default='Corte de cabello',
            help='Segunda variable de la plantilla'
        )
        parser.add_argument(
            '--var3',
            type=str,
            default='15/01 14:00',
            help='Tercera variable de la plantilla'
        )
        parser.add_argument(
            '--check-status',
            type=str,
            default=None,
            help='Verificar el estado de un mensaje usando su SID'
        )

    def handle(self, *args, **options):
        # Verificar estado de un mensaje
        if options['check_status']:
            self.check_message_status(options['check_status'])
            return
        
        phone = options['phone_number']
        template = options.get('template')
        simple_message = options.get('message')
        
        # Mostrar configuración
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('🔧 CONFIGURACIÓN TWILIO'))
        self.stdout.write('='*60)
        self.stdout.write(f"Account SID: {settings.TWILIO_ACCOUNT_SID[:10]}..." if settings.TWILIO_ACCOUNT_SID else "❌ No configurado")
        self.stdout.write(f"Auth Token: {'✅ Configurado' if settings.TWILIO_AUTH_TOKEN else '❌ No configurado'}")
        self.stdout.write(f"WhatsApp From: {settings.TWILIO_WHATSAPP_FROM}")
        self.stdout.write(f"Test Mode: {'✅ Activado' if settings.WHATSAPP_TEST_MODE else '❌ Desactivado'}")
        self.stdout.write('='*60 + '\n')
        
        # Enviar mensaje simple
        if simple_message:
            self.send_simple_message(phone, simple_message)
            return
        
        # Enviar template
        if template:
            self.send_template_message(phone, template, options)
            return
        
        # Si no se especificó nada, mostrar ayuda
        self.stdout.write(self.style.ERROR('❌ Debes especificar --template o --message'))
        self.stdout.write('\nEjemplos de uso:')
        self.stdout.write('  # Mensaje simple (sandbox):')
        self.stdout.write('  python manage.py test_whatsapp 0999999999 --message "Hola desde Liberi"')
        self.stdout.write('\n  # Con template:')
        self.stdout.write('  python manage.py test_whatsapp 0999999999 --template booking_created')
        self.stdout.write('\n  # Verificar estado:')
        self.stdout.write('  python manage.py test_whatsapp dummy --check-status SMxxxxxxxxxxxxx')
    
    def send_simple_message(self, phone, message):
        """Envía un mensaje simple"""
        self.stdout.write(f'\n📱 Enviando mensaje simple de WhatsApp via Twilio...')
        self.stdout.write(f'📞 Destinatario: {phone}')
        self.stdout.write(f'💬 Mensaje: {message}\n')
        
        log = WhatsAppService.send_simple_message(phone, message)
        self.show_result(log)
    
    def send_template_message(self, phone, template, options):
        """Envía un mensaje usando template"""
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
        
        self.stdout.write(f'\n📱 Enviando mensaje de WhatsApp via Twilio...')
        self.stdout.write(f'📞 Destinatario: {phone}')
        self.stdout.write(f'📝 Plantilla: {template}')
        self.stdout.write(f'📋 Variables: {variables}\n')
        
        # Enviar mensaje
        log = WhatsAppService.send_message(
            recipient_number=phone,
            template_name=template,
            variables=variables
        )
        
        self.show_result(log)
    
    def show_result(self, log):
        """Muestra el resultado del envío"""
        if log.status == 'sent':
            self.stdout.write(
                self.style.SUCCESS(f'✅ Mensaje enviado exitosamente')
            )
            self.stdout.write(f'🆔 Message SID: {log.message_id}')
            self.stdout.write(f'📊 Log ID: {log.id}')
            
            if settings.WHATSAPP_TEST_MODE:
                self.stdout.write(self.style.WARNING('\n⚠️  Estás en TEST MODE - no se envió mensaje real'))
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Error al enviar mensaje')
            )
            self.stdout.write(f'🔴 Estado: {log.get_status_display()}')
            if log.error_message:
                self.stdout.write(f'💬 Error: {log.error_message}')
        
        # Mostrar últimos logs
        self.stdout.write('\n📋 Últimos 5 logs de WhatsApp:')
        self.stdout.write('-' * 80)
        recent_logs = WhatsAppLog.objects.all()[:5]
        for l in recent_logs:
            status_icon = '✅' if l.status == 'sent' else '❌'
            self.stdout.write(
                f'{status_icon} {l.created_at.strftime("%Y-%m-%d %H:%M:%S")} | '
                f'{l.recipient} | {l.message_type} | {l.get_status_display()}'
            )
    
    def check_message_status(self, message_sid):
        """Verifica el estado de un mensaje"""
        self.stdout.write(f'\n🔍 Consultando estado del mensaje: {message_sid}\n')
        
        status = WhatsAppService.check_message_status(message_sid)
        
        if 'error' in status:
            self.stdout.write(self.style.ERROR(f'❌ Error: {status["error"]}'))
        else:
            self.stdout.write(self.style.SUCCESS('📊 Estado del mensaje:'))
            self.stdout.write(f'  SID: {status["sid"]}')
            self.stdout.write(f'  Estado: {status["status"]}')
            self.stdout.write(f'  Enviado: {status["date_sent"]}')
            self.stdout.write(f'  Actualizado: {status["date_updated"]}')
            if status.get('error_code'):
                self.stdout.write(self.style.WARNING(f'  Error Code: {status["error_code"]}'))
                self.stdout.write(self.style.WARNING(f'  Error Message: {status["error_message"]}'))