"""
Servicio alternativo de WhatsApp usando mensajes simples (sin templates).
Usar este servicio mientras los templates son aprobados por Meta.

Para usar en producción, cambiar a WhatsAppService con templates aprobados.
"""
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from apps.whatsapp_notifications.models import WhatsAppLog

logger = logging.getLogger(__name__)


class WhatsAppSimpleService:
    """
    Servicio de WhatsApp usando mensajes simples (sin templates).
    Solo funciona en Sandbox. Para producción, usar WhatsAppService con templates.
    """
    
    @staticmethod
    def _get_twilio_client():
        """Obtiene el cliente de Twilio configurado"""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            raise ValueError("Credenciales de Twilio no configuradas")
        
        return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    @staticmethod
    def format_phone_number(phone: str) -> str:
        """
        Formatea un número de teléfono al formato requerido por Twilio (sin +).
        
        Ejemplos:
            '0999123456' → '593999123456'
            '593999123456' → '593999123456'
            '+593999123456' → '593999123456'
        """
        # Limpiar número (solo dígitos)
        clean = ''.join(filter(str.isdigit, phone))
        
        # Si ya tiene código de país Ecuador, retornar
        if clean.startswith('593'):
            return clean
        
        # Remover 0 inicial si existe
        if clean.startswith('0'):
            clean = clean[1:]
        
        # Agregar código de país Ecuador
        return f'593{clean}'
    
    @staticmethod
    def send_booking_created(recipient_number: str, customer_name: str, service: str, datetime: str):
        """
        Notifica sobre una nueva reserva.
        
        Args:
            recipient_number: Número del proveedor
            customer_name: Nombre del cliente
            service: Nombre del servicio
            datetime: Fecha y hora de la reserva
        """
        message = f"""🔔 *Nueva Reserva - Liberi*

Cliente: {customer_name}
Servicio: {service}
Fecha/hora: {datetime}

Ingresa a la app para aceptar o rechazar esta solicitud.

_Mensaje automático de Liberi_"""
        
        return WhatsAppSimpleService._send_message(
            recipient_number=recipient_number,
            message_body=message,
            message_type='booking_created'
        )
    
    @staticmethod
    def send_booking_accepted(recipient_number: str, provider_name: str, service: str):
        """
        Notifica que la reserva fue aceptada.
        
        Args:
            recipient_number: Número del cliente
            provider_name: Nombre del proveedor
            service: Nombre del servicio
        """
        message = f"""✅ *¡Reserva Confirmada! - Liberi*

{provider_name} ha aceptado tu reserva de {service}.

Ingresa a la app para continuar con el pago.

_Mensaje automático de Liberi_"""
        
        return WhatsAppSimpleService._send_message(
            recipient_number=recipient_number,
            message_body=message,
            message_type='booking_accepted'
        )
    
    @staticmethod
    def send_payment_confirmed(recipient_number: str, customer_name: str, service: str):
        """
        Notifica que el pago fue confirmado.
        
        Args:
            recipient_number: Número del proveedor
            customer_name: Nombre del cliente
            service: Nombre del servicio
        """
        message = f"""💰 *¡Pago Confirmado! - Liberi*

{customer_name} ha pagado por tu servicio de {service}.

El dinero estará disponible en tu cuenta Liberi al completar el servicio.

_Mensaje automático de Liberi_"""
        
        return WhatsAppSimpleService._send_message(
            recipient_number=recipient_number,
            message_body=message,
            message_type='payment_confirmed'
        )
    
    @staticmethod
    def send_reminder(recipient_number: str, service: str, time: str):
        """
        Envía un recordatorio de servicio.
        
        Args:
            recipient_number: Número del cliente o proveedor
            service: Nombre del servicio
            time: Hora del servicio
        """
        message = f"""⏰ *Recordatorio - Liberi*

Tu servicio de {service} es en 1 hora a las {time}.

¡Nos vemos pronto!

_Mensaje automático de Liberi_"""
        
        return WhatsAppSimpleService._send_message(
            recipient_number=recipient_number,
            message_body=message,
            message_type='reminder'
        )
    
    @staticmethod
    def _send_message(recipient_number: str, message_body: str, message_type: str):
        """
        Envía un mensaje simple de WhatsApp.
        
        Args:
            recipient_number: Número de teléfono
            message_body: Texto del mensaje
            message_type: Tipo de mensaje (para logging)
        
        Returns:
            WhatsAppLog: Objeto con el registro del envío
        """
        # Modo de prueba
        if settings.WHATSAPP_TEST_MODE:
            log = WhatsAppLog.objects.create(
                recipient=recipient_number,
                message_type=message_type,
                status='sent',
                message_id='TEST_MODE',
                template_variables=[message_body],
                response=f"🧪 TEST MODE: '{message_type}' → {recipient_number}"
            )
            logger.info(f"🧪 TEST MODE: WhatsApp '{message_type}' a {recipient_number}")
            return log
        
        # Limpiar y formatear número
        clean_number = WhatsAppSimpleService.format_phone_number(recipient_number)
        
        try:
            client = WhatsAppSimpleService._get_twilio_client()
            
            logger.info(f"📱 Enviando WhatsApp simple:")
            logger.info(f"   Tipo: {message_type}")
            logger.info(f"   Destinatario: +{clean_number}")
            
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=f'whatsapp:+{clean_number}',
                body=message_body
            )
            
            log = WhatsAppLog.objects.create(
                recipient=clean_number,
                message_type=message_type,
                status='sent',
                message_id=message.sid,
                template_variables=[message_body],
                response=f"Twilio Status: {message.status}, SID: {message.sid}"
            )
            
            logger.info(f"✅ WhatsApp enviado exitosamente")
            logger.info(f"   Message SID: {message.sid}")
            logger.info(f"   Status: {message.status}")
            
            return log
            
        except TwilioRestException as e:
            error_msg = f"Twilio Error {e.code}: {e.msg}"
            logger.error(f"❌ {error_msg}")
            
            return WhatsAppLog.objects.create(
                recipient=clean_number,
                message_type=message_type,
                status='failed',
                template_variables=[message_body],
                error_message=error_msg
            )
            
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}", exc_info=True)
            return WhatsAppLog.objects.create(
                recipient=clean_number,
                message_type=message_type,
                status='failed',
                template_variables=[message_body],
                error_message=f"Error inesperado: {str(e)}"
            )


# Alias para facilitar la migración
# Cuando los templates estén aprobados, cambiar esto a WhatsAppService
WhatsAppServiceActive = WhatsAppSimpleService
