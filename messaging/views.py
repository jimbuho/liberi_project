from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from core.models import Booking
from .whatsapp import WhatsAppService

class SendWhatsAppView(APIView):
    """
    Envía notificaciones por WhatsApp
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        booking_id = request.data.get('booking_id')
        message_type = request.data.get('type', 'notification')
        
        if not booking_id:
            return Response(
                {'error': 'booking_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking = get_object_or_404(Booking, id=booking_id)
        
        # Verificar permisos
        if booking.customer != request.user and booking.provider != request.user:
            return Response(
                {'error': 'No autorizado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        whatsapp = WhatsAppService()
        
        if message_type == 'notification':
            result = whatsapp.send_booking_notification(booking)
        elif message_type == 'confirmation':
            result = whatsapp.send_booking_confirmation(booking)
        else:
            return Response(
                {'error': 'Tipo de mensaje inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if result['success']:
            return Response({'message': 'Mensaje enviado correctamente'})
        else:
            return Response(
                {'error': result.get('error', 'Error al enviar mensaje')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
