import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class PayPhoneService:
    """
    Servicio para integración con PayPhone (Ecuador)
    """
    def __init__(self):
        self.token = settings.PAYPHONE_TOKEN
        self.store_id = settings.PAYPHONE_CLIENT_ID
        self.api_url = settings.PAYPHONE_API_URL
    
    def create_payment(self, booking_id, amount, customer_email, customer_phone):
        """
        Crea una transacción de pago en PayPhone
        """
        try:
            payload = {
                "amount": float(amount),
                "amountWithoutTax": float(amount),
                "amountWithTax": 0,
                "tax": 0,
                "service": 0,
                "tip": 0,
                "currency": "USD",
                "reference": str(booking_id),
                "clientTransactionId": str(booking_id),
                "storeId": self.store_id,
                "email": customer_email,
                "phoneNumber": customer_phone,
                "documentId": "",
                "cancellationUrl": f"{settings.FRONTEND_URL}/booking/{booking_id}/cancelled",
                "responseUrl": f"{settings.FRONTEND_URL}/booking/{booking_id}/success",
            }
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'payment_url': data.get('paymentUrl'),
                'transaction_id': data.get('transactionId'),
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayPhone API Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, transaction_id):
        """
        Verifica el estado de un pago
        """
        try:
            verify_url = settings.PAYPHONE_URL_CONFIRM_PAYPHONE
            
            payload = {
                "id": transaction_id,
                "clientTxId": transaction_id
            }
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                verify_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'status': data.get('statusCode'),
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayPhone Verify Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
