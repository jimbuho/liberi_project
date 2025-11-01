from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from core.models import Booking, AuditLog
from .payphone import PayPhoneService

class CreatePaymentView(APIView):
    """
    Crea un pago con PayPhone
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        booking_id = request.data.get('booking_id')
        
        if not booking_id:
            return Response(
                {'error': 'booking_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        if booking.payment_status == 'paid':
            return Response(
                {'error': 'Esta reserva ya está pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payphone = PayPhoneService()
        result = payphone.create_payment(
            booking_id=booking.id,
            amount=booking.total_cost,
            customer_email=request.user.email,
            customer_phone=request.user.phone
        )
        
        if result['success']:
            booking.payment_method = 'payphone'
            booking.save()
            
            AuditLog.objects.create(
                user=request.user,
                action='Pago iniciado - PayPhone',
                metadata={'booking_id': str(booking.id), 'amount': str(booking.total_cost)}
            )
            
            return Response({
                'payment_url': result['payment_url'],
                'transaction_id': result['transaction_id']
            })
        else:
            return Response(
                {'error': result.get('error', 'Error al procesar el pago')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPaymentView(APIView):
    """
    Verifica el estado de un pago PayPhone
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        booking_id = request.data.get('booking_id')
        
        if not transaction_id or not booking_id:
            return Response(
                {'error': 'transaction_id y booking_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        payphone = PayPhoneService()
        result = payphone.verify_payment(transaction_id)
        
        if result['success']:
            payment_status = result['data'].get('statusCode')
            
            if payment_status == 3:  # Aprobado
                booking.payment_status = 'paid'
                booking.save()
                
                AuditLog.objects.create(
                    user=request.user,
                    action='Pago confirmado',
                    metadata={'booking_id': str(booking.id), 'transaction_id': transaction_id}
                )
                
                return Response({'status': 'paid', 'message': 'Pago confirmado'})
            else:
                return Response({'status': 'pending', 'message': 'Pago pendiente'})
        else:
            return Response(
                {'error': result.get('error', 'Error al verificar el pago')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BankTransferView(APIView):
    """
    Registra un comprobante de transferencia bancaria
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        booking_id = request.data.get('booking_id')
        transfer_reference = request.data.get('reference')
        
        if not booking_id or not transfer_reference:
            return Response(
                {'error': 'booking_id y reference son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        booking.payment_method = 'bank_transfer'
        booking.notes = f"Referencia: {transfer_reference}"
        booking.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='Transferencia bancaria registrada',
            metadata={
                'booking_id': str(booking.id),
                'reference': transfer_reference
            }
        )
        
        return Response({
            'message': 'Transferencia registrada. Pendiente de verificación.',
            'status': 'pending_verification'
        })
