import json
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from .models import WhatsAppLog


logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Servicio para enviar mensajes de WhatsApp usando Twilio
    """
    
    # Templates aprobados en Twilio Content Template Builder
    # IMPORTANTE: Actualizar estos Content SIDs después de crear y aprobar los templates
    TEMPLATES = {
        'booking_created': {
            'content_sid': 'HXc7292f5e0afc81cb3a70eb183ddc7d2f',
            'friendly_name': 'booking_created',
            'variables_count': 4,  # nombre_cliente, servicio, fecha_hora, booking_url
        },
        'booking_accepted': {
            'content_sid': 'HXac888f41014603ccab8e9670a3a864cb',
            'friendly_name': 'booking_accepted',
            'variables_count': 3,  # nombre_proveedor, servicio, booking_url
        },
        'payment_confirmed': {
            'content_sid': 'HX851573b0be6caf15988a289ca93b8c8e',
            'friendly_name': 'payment_confirmed',
            'variables_count': 2,  # nombre_cliente, servicio
        },
        'reminder': {
            'content_sid': 'HX214f1e711934557e5b84c963cc2219e1',
            'friendly_name': 'reminder',
            'variables_count': 3,  # servicio, hora, booking_url
        },
    }
    
    @staticmethod
    def _get_twilio_client():
        """Obtiene el cliente de Twilio configurado"""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            raise ValueError("Credenciales de Twilio no configuradas")
        
        return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    @staticmethod
    def send_message(recipient_number: str, template_name: str, variables: list):
        """
        Envía un mensaje usando Twilio WhatsApp API con Content Templates.
        
        Args:
            recipient_number: Número de teléfono con código de país (ej: 593999999999 o 0999999999)
            template_name: Nombre del template (booking_created, booking_accepted, etc.)
            variables: Lista de variables para el template en orden:
                       - booking_created: [nombre_cliente, servicio, fecha_hora, booking_url]
                       - booking_accepted: [nombre_proveedor, servicio, booking_url]
                       - payment_confirmed: [nombre_cliente, servicio]
                       - reminder: [servicio, hora, booking_url]
        
        Returns:
            WhatsAppLog: Objeto con el registro del envío
            
        Example:
            >>> log = WhatsAppService.send_message(
            ...     recipient_number='0999123456',
            ...     template_name='booking_created',
            ...     variables=[
            ...         'Juan Pérez',
            ...         'Corte de cabello',
            ...         '15/01 14:00',
            ...         'https://liberi.app/provider/bookings/abc123'
            ...     ]
            ... )
        """
        # Modo de prueba - no hace llamadas reales
        if settings.WHATSAPP_TEST_MODE:
            log = WhatsAppLog.objects.create(
                recipient=recipient_number,
                message_type=template_name,
                status='sent',
                message_id='TEST_MODE',
                response=f"🧪 TEST MODE: '{template_name}' → {variables}"
            )
            logger.info(f"🧪 TEST MODE: WhatsApp '{template_name}' a {recipient_number}")
            logger.info(f"   Variables: {variables}")
            return log

        # Validar template existe
        if template_name not in WhatsAppService.TEMPLATES:
            logger.error(f"❌ Template desconocido: {template_name}")
            return WhatsAppService._create_error_log(
                recipient_number,
                template_name,
                f"Template '{template_name}' no encontrado. Templates disponibles: {list(WhatsAppService.TEMPLATES.keys())}"
            )
        
        # Validar Content SID configurado
        template_info = WhatsAppService.TEMPLATES[template_name]
        content_sid = template_info['content_sid']
        
        if content_sid.startswith('HXxxxx'):
            logger.error(f"❌ Content SID no configurado para '{template_name}'")
            return WhatsAppService._create_error_log(
                recipient_number,
                template_name,
                f"Content SID para '{template_name}' no ha sido actualizado. "
                f"Crea el template en Twilio y actualiza el Content SID en services.py"
            )
        
        # Validar número correcto de variables
        expected_vars = template_info['variables_count']
        if len(variables) != expected_vars:
            logger.warning(
                f"⚠️ Template '{template_name}' espera {expected_vars} variables, "
                f"pero se recibieron {len(variables)}"
            )
        
        # Limpiar y formatear número
        clean_number = WhatsAppService.format_phone_number(recipient_number)
        
        try:
            # Obtener cliente de Twilio
            client = WhatsAppService._get_twilio_client()
            
            # ============================================
            # FIX CRÍTICO: Twilio requiere JSON string
            # ============================================
            # Preparar variables en formato Twilio: {"1": "valor1", "2": "valor2", ...}
            content_variables_dict = {
                str(i + 1): str(var) for i, var in enumerate(variables)
            }
            
            # Convertir a JSON string (ESTE ES EL FIX)
            content_variables_json = json.dumps(content_variables_dict)
            
            logger.info(f"📱 Enviando WhatsApp via Twilio:")
            logger.info(f"   Template: {template_name}")
            logger.info(f"   Destinatario: +{clean_number}")
            logger.info(f"   Variables Dict: {content_variables_dict}")
            logger.info(f"   Variables JSON: {content_variables_json}")
            
            # ============================================
            # Logging detallado de la petición a Twilio
            # ============================================
            logger.info("-- BEGIN Twilio API Request --")
            logger.info(f"POST Request: https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json")
            logger.info("Headers:")
            logger.info("Content-Type : application/x-www-form-urlencoded")
            logger.info("Accept : application/json")
            logger.info(f"User-Agent : twilio-python/9.8.6 (Linux x86_64) Python/3.12.12")
            logger.info("X-Twilio-Client : python-9.8.6")
            logger.info("Accept-Charset : utf-8")
            logger.info("-- END Twilio API Request --")
            
            # Enviar mensaje usando Content Template con JSON string
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=f'whatsapp:+{clean_number}',
                content_sid=content_sid,
                content_variables=content_variables_json  # <- AQUÍ ESTÁ EL FIX: JSON string
            )
            
            logger.info(f"Response Status Code: {message.status}")
            
            # Crear log exitoso
            log = WhatsAppLog.objects.create(
                recipient=clean_number,
                message_type=template_name,
                status='sent',
                message_id=message.sid,
                response=f"Twilio Status: {message.status}, SID: {message.sid}"
            )
            
            logger.info(f"✅ WhatsApp enviado exitosamente")
            logger.info(f"   Message SID: {message.sid}")
            logger.info(f"   Status: {message.status}")
            
            return log
            
        except TwilioRestException as e:
            error_msg = f"Twilio Error {e.code}: {e.msg}"
            logger.error(f"Response Status Code: 400")
            logger.error(f"Response Headers: {getattr(e, 'headers', {})}")
            logger.error(f"❌ {error_msg}")
            
            # Errores comunes y sus soluciones
            error_hints = {
                21211: "El número no está en el sandbox. Envía 'join plan-cover' al +1 415 523 8886",
                21408: "El número está bloqueado o no acepta mensajes",
                21656: "Content Variables inválidas. Verifica formato JSON y que coincidan con el template",
                63016: "Content SID inválido. Verifica que el template esté aprobado",
                63017: "Variables incorrectas. Verifica el número de variables del template",
            }
            
            hint = error_hints.get(e.code, '')
            if hint:
                logger.error(f"💡 Solución: {hint}")
            
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
                f"{error_msg}. {hint}" if hint else error_msg
            )
            
        except ValueError as e:
            logger.error(f"❌ Error de configuración: {e}")
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
                str(e)
            )
            
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}", exc_info=True)
            return WhatsAppService._create_error_log(
                clean_number,
                template_name,
                f"Error inesperado: {str(e)}"
            )
    
    @staticmethod
    def send_simple_message(recipient_number: str, message_body: str):
        """
        Envía un mensaje simple sin template (solo para testing en sandbox).
        
        IMPORTANTE: Los mensajes simples solo funcionan en el sandbox de Twilio.
        Para producción, debes usar templates aprobados con send_message().
        
        Args:
            recipient_number: Número de teléfono
            message_body: Texto del mensaje
        
        Returns:
            WhatsAppLog: Objeto con el registro del envío
        """
        if settings.WHATSAPP_TEST_MODE:
            log = WhatsAppLog.objects.create(
                recipient=recipient_number,
                message_type='simple_message',
                status='sent',
                message_id='TEST_MODE',
                response=f"🧪 TEST MODE: Mensaje simple: {message_body}"
            )
            logger.info(f"🧪 TEST MODE: Mensaje simple a {recipient_number}")
            return log
        
        clean_number = WhatsAppService.format_phone_number(recipient_number)
        
        try:
            client = WhatsAppService._get_twilio_client()
            
            logger.info(f"📱 Enviando mensaje simple via Twilio:")
            logger.info(f"   Destinatario: +{clean_number}")
            logger.info(f"   Mensaje: {message_body[:50]}...")
            
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=f'whatsapp:+{clean_number}',
                body=message_body
            )
            
            log = WhatsAppLog.objects.create(
                recipient=clean_number,
                message_type='simple_message',
                status='sent',
                message_id=message.sid,
                response=f"Twilio Status: {message.status}, SID: {message.sid}"
            )
            
            logger.info(f"✅ Mensaje simple enviado (SID: {message.sid})")
            return log
            
        except TwilioRestException as e:
            logger.error(f"❌ Error Twilio: {e.msg} (Code: {e.code})")
            return WhatsAppService._create_error_log(
                clean_number,
                'simple_message',
                f"Twilio Error {e.code}: {e.msg}"
            )
            
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje simple: {e}")
            return WhatsAppService._create_error_log(
                clean_number,
                'simple_message',
                str(e)
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
        Formatea un número de teléfono al formato requerido por Twilio (sin +).
        
        Ejemplos:
            '0999123456' → '593999123456'
            '593999123456' → '593999123456'
            '+593999123456' → '593999123456'
            '999123456' → '593999123456'
        
        Args:
            phone: Número de teléfono en cualquier formato
            
        Returns:
            str: Número limpio con código de país Ecuador (ej: 593999123456)
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
    def check_message_status(message_sid: str):
        """
        Consulta el estado actual de un mensaje en Twilio.
        
        Estados posibles:
        - queued: En cola
        - sent: Enviado a WhatsApp
        - delivered: Entregado al destinatario
        - read: Leído por el destinatario
        - failed: Falló el envío
        - undelivered: No se pudo entregar
        
        Args:
            message_sid: SID del mensaje de Twilio (ej: 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
            
        Returns:
            dict: Información del estado del mensaje
        """
        try:
            client = WhatsAppService._get_twilio_client()
            message = client.messages(message_sid).fetch()
            
            return {
                'sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'price': message.price,
                'price_unit': message.price_unit,
                'date_sent': message.date_sent,
                'date_updated': message.date_updated,
                'to': message.to,
                'from': message.from_,
            }
            
        except TwilioRestException as e:
            logger.error(f"❌ Error consultando mensaje: {e.msg} (Code: {e.code})")
            return {
                'error': f"Twilio Error {e.code}: {e.msg}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error consultando estado del mensaje: {e}")
            return {
                'error': str(e)
            }
    
    @staticmethod
    def get_template_info(template_name: str) -> dict:
        """
        Obtiene información sobre un template.
        
        Args:
            template_name: Nombre del template
            
        Returns:
            dict: Información del template o None si no existe
        """
        return WhatsAppService.TEMPLATES.get(template_name)
    
    @staticmethod
    def list_templates() -> list:
        """
        Lista todos los templates disponibles.
        
        Returns:
            list: Lista de nombres de templates
        """
        return list(WhatsAppService.TEMPLATES.keys())
    
    @staticmethod
    def validate_configuration() -> dict:
        """
        Valida la configuración de Twilio WhatsApp.
        
        Returns:
            dict: Resultado de la validación con warnings y errors
        """
        errors = []
        warnings = []
        
        # Validar credenciales
        if not settings.TWILIO_ACCOUNT_SID:
            errors.append("TWILIO_ACCOUNT_SID no configurado")
        elif not settings.TWILIO_ACCOUNT_SID.startswith('AC'):
            errors.append("TWILIO_ACCOUNT_SID debe empezar con 'AC'")
        
        if not settings.TWILIO_AUTH_TOKEN:
            errors.append("TWILIO_AUTH_TOKEN no configurado")
        
        if not settings.TWILIO_WHATSAPP_FROM:
            errors.append("TWILIO_WHATSAPP_FROM no configurado")
        elif not settings.TWILIO_WHATSAPP_FROM.startswith('whatsapp:+'):
            errors.append("TWILIO_WHATSAPP_FROM debe tener formato 'whatsapp:+14155238886'")
        
        # Validar templates
        for name, info in WhatsAppService.TEMPLATES.items():
            if info['content_sid'].startswith('HXxxxx'):
                warnings.append(f"Content SID no configurado para template '{name}'")
        
        # Validar modo test
        if settings.WHATSAPP_TEST_MODE:
            warnings.append("WHATSAPP_TEST_MODE activado - mensajes no se enviarán realmente")
        
        # Intentar conexión
        if not errors:
            try:
                client = WhatsAppService._get_twilio_client()
                account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
                logger.info(f"✅ Conexión exitosa con Twilio (Account: {account.friendly_name})")
            except Exception as e:
                errors.append(f"No se pudo conectar a Twilio: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'test_mode': settings.WHATSAPP_TEST_MODE,
            'templates_configured': sum(
                1 for t in WhatsAppService.TEMPLATES.values() 
                if not t['content_sid'].startswith('HXxxxx')
            ),
            'total_templates': len(WhatsAppService.TEMPLATES),
        }