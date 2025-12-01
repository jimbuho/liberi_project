import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Servicio para enviar mensajes por WhatsApp usando Twilio
    """
    def __init__(self):
        self.phone_number = settings.WHATSAPP_PHONE_NUMBER
        self.token = settings.WHATSAPP_TOKEN
        self.account_sid = settings.WHATSAPP_ACCOUNT_SID
    
    def send_message(self, to_number, message):
        """
        Envía un mensaje de WhatsApp usando Twilio
        """
        try:
            # Formato de número internacional
            if not to_number.startswith('+'):
                to_number = f'+593{to_number}'
            
            # URL de Twilio WhatsApp API
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            
            data = {
                'From': f'whatsapp:{self.phone_number}',
                'To': f'whatsapp:{to_number}',
                'Body': message
            }
            
            response = requests.post(
                url,
                data=data,
                auth=(self.account_sid, self.token),
                timeout=10
            )
            
            response.raise_for_status()
            
            return {
                'success': True,
                'data': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_booking_notification(self, booking):
        """
        Notifica al proveedor sobre una nueva reserva
        """
        message = f"""
🔔 *Nueva Reserva - Liberi*

Cliente: {booking.customer.get_full_name()}
Servicios: {', '.join([s.get('name', '') for s in booking.service_list])}
Fecha: {booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
Dirección: {booking.location.address if booking.location else 'No especificada'}
Total: ${booking.total_cost}

Por favor confirma o rechaza esta reserva desde la app.
"""
        
        return self.send_message(booking.provider.phone, message)
    
    def send_booking_confirmation(self, booking):
        """
        Confirma al cliente que su reserva fue aceptada
        """
        message = f"""
✅ *Reserva Confirmada - Liberi*

Tu reserva ha sido aceptada por {booking.provider.get_full_name()}.

Fecha: {booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
Servicios: {', '.join([s.get('name', '') for s in booking.service_list])}
Total: ${booking.total_cost}

El proveedor llegará a la dirección acordada.
Teléfono del proveedor: {booking.provider.phone}
"""
        
        return self.send_message(booking.customer.phone, message)
