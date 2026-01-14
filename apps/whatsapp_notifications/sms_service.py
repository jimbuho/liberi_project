"""
Servicio de notificaciones SMS usando Twilio.
Reemplaza WhatsApp para mayor confiabilidad y simplicidad.
"""
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from .models import WhatsAppLog  # Reutilizamos el modelo para mantener historial

logger = logging.getLogger(__name__)


class SMSService:
    """Servicio para enviar notificaciones por SMS usando Twilio"""
    
    @staticmethod
    def _get_twilio_client():
        """Obtiene el cliente de Twilio configurado"""
        return Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
    
    @staticmethod
    def format_phone_number(phone: str) -> str:
        """
        Formatea un número de teléfono al formato requerido por Twilio.
        
        Ejemplos:
            '0999123456' → '+593999123456'
            '593999123456' → '+593999123456'
            '+593999123456' → '+593999123456'
        
        Args:
            phone: Número de teléfono en cualquier formato
            
        Returns:
            str: Número con formato internacional (+593...)
        """
        # Limpiar espacios y caracteres especiales
        phone = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Si ya tiene +, retornar
        if phone.startswith('+'):
            return phone
        
        # Si empieza con 0, reemplazar por código de país Ecuador
        if phone.startswith('0'):
            return f'+593{phone[1:]}'
        
        # Si no tiene código de país, agregar Ecuador
        if not phone.startswith('593'):
            return f'+593{phone}'
        
        # Si tiene código pero no +
        return f'+{phone}'
    
    @staticmethod
    def send_booking_created(recipient_number: str, client_name: str, service_name: str, datetime_str: str):
        """
        Envía notificación de nueva reserva creada.
        
        Args:
            recipient_number: Número del proveedor
            client_name: Nombre del cliente
            service_name: Nombre del servicio
            datetime_str: Fecha y hora de la reserva
        """
        message = f"""
🔔 Nueva Solicitud de Reserva - Liberi App

Cliente: {client_name}
Servicio: {service_name}
Fecha/Hora: {datetime_str}

Ingresa a tu dashboard para aceptar o rechazar:
https://liberi.app/provider/dashboard/

¡Gracias por usar Liberi!
        """.strip()
        
        return SMSService.send_message(recipient_number, message, 'booking_created')
    
    @staticmethod
    def send_booking_accepted(recipient_number: str, provider_name: str, service_name: str, booking_id: str):
        """
        Envía notificación de reserva aceptada.
        
        Args:
            recipient_number: Número del cliente
            provider_name: Nombre del proveedor
            service_name: Nombre del servicio
            booking_id: ID de la reserva
        """
        message = f"""
✅ ¡Tu reserva ha sido aceptada! - Liberi App

Proveedor: {provider_name}
Servicio: {service_name}

Ver detalles y pagar:
https://liberi.app/bookings/{booking_id}/

¡Gracias por confiar en Liberi!
        """.strip()
        
        return SMSService.send_message(recipient_number, message, 'booking_accepted')
    
    @staticmethod
    def send_payment_confirmed(recipient_number: str, client_name: str, service_name: str):
        """
        Envía notificación de pago confirmado.
        
        Args:
            recipient_number: Número del proveedor
            client_name: Nombre del cliente
            service_name: Nombre del servicio
        """
        message = f"""
💰 Pago Confirmado - Liberi App

Cliente: {client_name}
Servicio: {service_name}

El cliente ha completado el pago.
Puedes ver los detalles en tu dashboard.

¡Gracias por usar Liberi!
        """.strip()
        
        return SMSService.send_message(recipient_number, message, 'payment_confirmed')
    
    @staticmethod
    def send_service_reminder(recipient_number: str, service_name: str, time_str: str, booking_id: str):
        """
        Envía recordatorio de servicio próximo.
        
        Args:
            recipient_number: Número del cliente
            service_name: Nombre del servicio
            time_str: Hora del servicio
            booking_id: ID de la reserva
        """
        message = f"""
⏰ Recordatorio de Servicio - Liberi App

Servicio: {service_name}
Hora: {time_str}

Ver detalles:
https://liberi.app/bookings/{booking_id}/

¡Te esperamos!
        """.strip()
        
        return SMSService.send_message(recipient_number, message, 'reminder')
    
    @staticmethod
    def send_message(recipient_number: str, message_body: str, message_type: str = 'general'):
        """
        Envía un mensaje SMS.
        
        Args:
            recipient_number: Número de teléfono del destinatario
            message_body: Contenido del mensaje
            message_type: Tipo de mensaje para logging
            
        Returns:
            WhatsAppLog: Objeto con el registro del envío
        """
        try:
            # Formatear número
            formatted_number = SMSService.format_phone_number(recipient_number)
            
            # Obtener cliente Twilio
            client = SMSService._get_twilio_client()
            
            # Enviar SMS
            message = client.messages.create(
                from_=settings.TWILIO_SMS_FROM,
                to=formatted_number,
                body=message_body
            )
            
            # Crear log
            log = WhatsAppLog.objects.create(
                recipient=formatted_number,
                message_type=message_type,
                message_id=message.sid,
                status='sent',
                response=str({
                    'sid': message.sid,
                    'status': message.status,
                    'to': message.to,
                    'from': message.from_,
                    'body': message_body[:100],  # Primeros 100 caracteres
                })
            )
            
            logger.info(f"SMS enviado exitosamente a {formatted_number}. SID: {message.sid}")
            return log
            
        except TwilioRestException as e:
            logger.error(f"Error de Twilio al enviar SMS: {e.msg} (Código: {e.code})")
            return SMSService._create_error_log(
                recipient_number,
                message_type,
                f"Error {e.code}: {e.msg}"
            )
            
        except Exception as e:
            logger.error(f"Error inesperado al enviar SMS: {str(e)}")
            return SMSService._create_error_log(
                recipient_number,
                message_type,
                f"Error inesperado: {str(e)}"
            )
    
    @staticmethod
    def _create_error_log(recipient: str, message_type: str, error_message: str):
        """Crea un log de error"""
        return WhatsAppLog.objects.create(
            recipient=recipient,
            message_type=message_type,
            status='failed',
            error_message=error_message
        )
    
    @staticmethod
    def check_message_status(message_sid: str):
        """
        Consulta el estado actual de un mensaje en Twilio.
        
        Args:
            message_sid: SID del mensaje de Twilio
            
        Returns:
            dict: Información del estado del mensaje
        """
        try:
            client = SMSService._get_twilio_client()
            message = client.messages(message_sid).fetch()
            
            return {
                'sid': message.sid,
                'status': message.status,
                'to': message.to,
                'from': message.from_,
                'date_sent': message.date_sent,
                'date_updated': message.date_updated,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'price': message.price,
                'price_unit': message.price_unit,
            }
            
        except TwilioRestException as e:
            logger.error(f"Error al consultar estado del mensaje: {e.msg}")
            return {
                'error': True,
                'error_code': e.code,
                'error_message': e.msg
            }
    
    @staticmethod
    def validate_configuration():
        """
        Valida la configuración de Twilio SMS.
        
        Returns:
            dict: Resultado de la validación con warnings y errors
        """
        errors = []
        warnings = []
        
        # Verificar credenciales
        if not settings.TWILIO_ACCOUNT_SID:
            errors.append("TWILIO_ACCOUNT_SID no configurado")
        if not settings.TWILIO_AUTH_TOKEN:
            errors.append("TWILIO_AUTH_TOKEN no configurado")
        if not settings.TWILIO_SMS_FROM:
            errors.append("TWILIO_SMS_FROM no configurado")
        elif not settings.TWILIO_SMS_FROM.startswith('+'):
            errors.append("TWILIO_SMS_FROM debe tener formato '+13853344436'")
        
        # Si hay errores críticos, no continuar
        if errors:
            return {
                'valid': False,
                'errors': errors,
                'warnings': warnings
            }
        
        # Intentar conectar con Twilio
        try:
            client = SMSService._get_twilio_client()
            account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
            
            if account.status != 'active':
                warnings.append(f"Cuenta de Twilio no está activa: {account.status}")
            
        except Exception as e:
            errors.append(f"No se pudo conectar con Twilio: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
