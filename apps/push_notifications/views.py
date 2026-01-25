from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .services import OneSignalService
import logging


logger = logging.getLogger(__name__)


class RegisterDeviceView(APIView):
    """
    Registra un dispositivo para recibir push notifications
    
    POST /api/push/register/
    {
        "player_id": "abc123...",
        "device_type": "Web"  // opcional
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        player_id = request.data.get('player_id')
        device_type = request.data.get('device_type', 'Web')
        
        if not player_id:
            return Response(
                {'error': 'player_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subscription = OneSignalService.register_device(
                user=request.user,
                player_id=player_id,
                device_type=device_type
            )
            
            return Response({
                'success': True,
                'message': 'Dispositivo registrado correctamente',
                'subscription_id': subscription.id
            })
            
        except Exception as e:
            logger.error(f"Error registrando dispositivo: {e}", exc_info=True)
            return Response(
                {'error': f'Error al registrar dispositivo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UnregisterDeviceView(APIView):
    """
    Desactiva un dispositivo
    
    POST /api/push/unregister/
    {
        "player_id": "abc123..."
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        player_id = request.data.get('player_id')
        
        if not player_id:
            return Response(
                {'error': 'player_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            success = OneSignalService.unregister_device(player_id)
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Dispositivo desactivado correctamente'
                })
            else:
                return Response(
                    {'error': 'Dispositivo no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Error desactivando dispositivo: {e}", exc_info=True)
            return Response(
                {'error': f'Error al desactivar dispositivo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendTestNotificationView(APIView):
    """
    Envía una notificación de prueba al usuario actual
    
    POST /api/push/test/
    {
        "title": "Test",
        "message": "Mensaje de prueba"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        title = request.data.get('title', '🧪 Notificación de Prueba')
        message = request.data.get('message', 'Esta es una notificación de prueba desde Liberi')
        
        try:
            log = OneSignalService.send_notification(
                user=request.user,
                title=title,
                message=message,
                notification_type='test',
                url=f"{request.scheme}://{request.get_host()}/dashboard/"
            )
            
            if log.status == 'sent':
                return Response({
                    'success': True,
                    'message': 'Notificación enviada correctamente',
                    'log_id': log.id,
                    'onesignal_id': log.onesignal_id
                })
            else:
                return Response({
                    'success': False,
                    'error': log.error_message
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error enviando notificación de prueba: {e}", exc_info=True)
            return Response(
                {'error': f'Error al enviar notificación: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
