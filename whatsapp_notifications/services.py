import requests
import logging
from django.conf import settings
from .models import WhatsAppLog


logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Servicio para enviar mensajes de WhatsApp usando la Cloud API de Meta
    """
    BASE_URL = "https://graph.facebook.com/v20.0"
    
    @staticmethod
    def send_message(recipient_number: str, template_name: str, variables: list):
        """
        Envía un mensaje usando una plantilla oficial de WhatsApp Cloud API.
        
        Args:
            recipient_number: Número de teléfono con código de país (ej: 593999999999)
            template_name: Nombre de la plantilla aprobada en WhatsApp Business
            variables: Lista de variables para la plantilla (ej: ['Juan', 'Corte de cabello', '15/01 14:00'])
        
        Returns:
            WhatsAppLog: Objeto con el registro del envío
        """
        # Modo de prueba - no hace llamadas reales
        if getattr(settings, 'WHATSAPP_TEST_MODE', False):
            log = WhatsAppLog.objects.create(
                recipient=recipient_number,
                message_type=template_name,
                status='test_success',
                response=f"TEST MODE: Mensaje '{template_name}' con variables {variables}"
            )
            return log

        # Validar configuración
        if not settings.WHATSAPP_ACCESS_TOKEN:
            logger.error("WHATSAPP_ACCESS_TOKEN no configurado")
            return WhatsAppService._create_error_log(
                recipient_number,
                template_name,
                "Token de acceso no configurado"
            )
        
        if not settings.WHATSAPP_PHONE_NUMBER_ID:
            logger.error("WHATSAPP_PHONE_NUMBER_ID no configurado")
            return WhatsAppService._create_error_log(
                recipient_number,
                template_name,
                "Phone Number ID no configurado"
            )
        
        # Limpiar número de teléfono (solo dígitos)
        clean_number = ''.join(filter(str.isdigit, recipient_number))
        
        # Si el número no tiene código de país, agregar Ecuador (+593)
        if not clean_number.startswith('593'):
            # Remover el 0 inicial si existe
            if clean_number.startswith('0'):
                clean_number = clean_number[1:]
            clean_number = f'593{clean_number}'
        
        # Construir URL
        url = f"{WhatsAppService.BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        # Headers
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Payload
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "es"},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(var)} for var in variables]
                }]
            }
        }
        
        logger.info(f"Enviando WhatsApp a {clean_number} usando template '{template_name}'")
        logger.debug(f"Payload: {payload}")
        
        try:
            # Realizar request
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=15
            )
            
            logger.info(f"WhatsApp API Status: {response.status_code}")
            logger.debug(f"WhatsApp API Response: {response.text}")
            
            response_data = response.json()
            
            # Determinar status
            if response.status_code == 200 and 'messages' in response_data:
                message_id = response_data.get('messages', [{}])[0].get('id', '')
                log = WhatsAppLog.objects.create(
                    recipient=clean_number,
                    message_type=template_name,
                    status='sent',
                    response=response.text,
                    message_id=message_id
                )
                logger.info(f"✅ WhatsApp enviado exitosamente a {clean_number} (ID: {message_id})")
            else:
                error_msg = response_data.get('error', {}).get('message', 'Error desconocido')
                log = WhatsAppLog.objects.create(
                    recipient=clean_number,
                    message_type=template_name,
                    status='failed',
                    response=response.text,
                    error_message=error_msg
                )
                logger.error(f"❌ Error enviando WhatsApp: {error_msg}")
            
            return log
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout enviando WhatsApp a {clean_number}")
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
                "Timeout de conexión"
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de conexión: {e}")
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
                f"Error de conexión: {str(e)}"
            )
            
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}", exc_info=True)
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
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
    def format_phone_number(phone: str) -> str:
        """
        Formatea un número de teléfono al formato requerido por WhatsApp
        
        Args:
            phone: Número de teléfono en cualquier formato
            
        Returns:
            str: Número limpio con código de país (ej: 593999999999)
        """
        # Limpiar número (solo dígitos)
        clean = ''.join(filter(str.isdigit, phone))
        
        # Si ya tiene código de país, retornar
        if clean.startswith('593'):
            return clean
        
        # Remover 0 inicial si existe
        if clean.startswith('0'):
            clean = clean[1:]
        
        # Agregar código de Ecuador
        return f'593{clean}'