from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone

from ..serializers.bookings import BookingListSerializer, BookingDetailSerializer
from ..permissions import IsProvider, IsBookingParticipant
from ..utils import success_response, error_response, paginated_response
from apps.core.models import Booking


class ProviderBookingListView(APIView):
    """
    GET /api/v1/provider/bookings/
    
    Listar reservas recibidas por el proveedor con filtros
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        # Filtros
        status_filter = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        # Query base
        bookings = Booking.objects.filter(provider=request.user).select_related(
            'customer', 'location', 'provider_location', 'customer__profile'
        ).order_by('-created_at')
        
        # Aplicar filtros
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        if date_from:
            bookings = bookings.filter(scheduled_time__gte=date_from)
        
        if date_to:
            bookings = bookings.filter(scheduled_time__lte=date_to)
        
        # Serializar con paginación
        return paginated_response(
            bookings,
            BookingListSerializer,
            request
        )


class BookingAcceptView(APIView):
    """
    POST /api/v1/provider/bookings/{booking_id}/accept/
    
    Aceptar una reserva pendiente
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id, provider=request.user)
        except Booking.DoesNotExist:
            return error_response(
                "Reserva no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que esté pendiente
        if booking.status != 'pending':
            return error_response(
                f"No puedes aceptar una reserva con estado: {booking.get_status_display()}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que el pago esté confirmado
        if booking.payment_status != 'paid':
            return error_response(
                "Solo puedes aceptar reservas con pago confirmado",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Aceptar reserva
        booking.status = 'accepted'
        booking.save()
        
        # Crear notificación para el cliente
        from apps.core.models import Notification
        Notification.objects.create(
            user=booking.customer,
            notification_type='booking_accepted',
            title='✅ Reserva Aceptada',
            message=f'{request.user.get_full_name()} ha aceptado tu reserva. Te esperamos el {booking.scheduled_time.strftime("%d/%m/%Y a las %H:%M")}.',
            booking=booking,
            action_url=f'/bookings/{booking.id}/'
        )
        
        # Enviar notificación WhatsApp si está configurado
        try:
            from apps.whatsapp_notifications.services import send_booking_accepted
            send_booking_accepted(booking)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando WhatsApp: {e}")
        
        serializer = BookingDetailSerializer(booking, context={'request': request})
        return success_response(
            data=serializer.data,
            message="Reserva aceptada exitosamente"
        )


class BookingRejectView(APIView):
    """
    POST /api/v1/provider/bookings/{booking_id}/reject/
    
    Rechazar una reserva pendiente
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id, provider=request.user)
        except Booking.DoesNotExist:
            return error_response(
                "Reserva no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que esté pendiente
        if booking.status != 'pending':
            return error_response(
                f"No puedes rechazar una reserva con estado: {booking.get_status_display()}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        
        # Rechazar reserva
        booking.status = 'cancelled'
        booking.notes = f"Rechazada por proveedor. Motivo: {reason}" if reason else "Rechazada por proveedor"
        booking.save()
        
        # Crear notificación para el cliente
        from apps.core.models import Notification
        Notification.objects.create(
            user=booking.customer,
            notification_type='booking_rejected',
            title='❌ Reserva Cancelada',
            message=f'Tu reserva ha sido cancelada por el proveedor. {reason}',
            booking=booking,
            action_url=f'/bookings/{booking.id}/'
        )
        
        # Si ya pagó, iniciar proceso de reembolso
        if booking.payment_status == 'paid':
            booking.payment_status = 'refunded'
            booking.save()
            # TODO: Procesar reembolso automático
        
        return success_response(
            message="Reserva rechazada exitosamente"
        )


class BookingCompleteWithCodeView(APIView):
    """
    POST /api/v1/provider/bookings/{booking_id}/complete-with-code/
    
    Completar servicio usando el código de verificación del cliente
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id, provider=request.user)
        except Booking.DoesNotExist:
            return error_response(
                "Reserva no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que esté aceptada
        if booking.status != 'accepted':
            return error_response(
                "Solo puedes completar reservas aceptadas",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar código
        completion_code = request.data.get('completion_code', '').strip()
        
        if not completion_code:
            return error_response(
                "Código de completación requerido",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if not booking.verify_completion_code(completion_code):
            return error_response(
                "Código inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Marcar como completado por proveedor
        booking.provider_completed_at = timezone.now()
        
        # Si ambos han marcado como completado, cambiar estado
        if booking.customer_completed_at:
            booking.status = 'completed'
        
        booking.save()
        
        # Crear notificación
        from apps.core.models import Notification
        Notification.objects.create(
            user=booking.customer,
            notification_type='booking_completed',
            title='✅ Servicio Completado',
            message=f'El proveedor ha confirmado la finalización del servicio. ¡Gracias por usar Liberi!',
            booking=booking,
            action_url=f'/bookings/{booking.id}/'
        )
        
        serializer = BookingDetailSerializer(booking, context={'request': request})
        return success_response(
            data=serializer.data,
            message="Servicio completado exitosamente"
        )


class VerificationDocumentsView(APIView):
    """
    POST /api/v1/provider/verification/documents/
    
    Subir documentos de verificación de identidad
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request):
        try:
            provider_profile = request.user.provider_profile
        except:
            return error_response(
                "Perfil de proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que tenga los 3 documentos
        if 'id_card_front' not in request.FILES:
            return error_response(
                "Falta cédula frontal",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if 'id_card_back' not in request.FILES:
            return error_response(
                "Falta cédula posterior",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if 'selfie_with_id' not in request.FILES:
            return error_response(
                "Falta selfie con cédula",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Guardar documentos
        provider_profile.id_card_front = request.FILES['id_card_front']
        provider_profile.id_card_back = request.FILES['id_card_back']
        provider_profile.selfie_with_id = request.FILES['selfie_with_id']
        provider_profile.save()
        
        # Triggear validación automática
        from apps.core.verification import trigger_validation_if_eligible
        triggered = trigger_validation_if_eligible(request.user)
        
        message = "Documentos subidos exitosamente."
        if triggered:
            message += " Tu perfil está en proceso de verificación."
        
        return success_response(
            data={
                'status': provider_profile.status,
                'triggered_verification': triggered,
                'documents_verified': provider_profile.documents_verified
            },
            message=message
        )


class RequestReverificationView(APIView):
    """
    POST /api/v1/provider/verification/request-reverification/
    
    Solicitar re-verificación después de un rechazo
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request):
        try:
            provider_profile = request.user.provider_profile
        except:
            return error_response(
                "Perfil de proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que esté rechazado
        if provider_profile.status != 'rejected':
            return error_response(
                "Solo puedes solicitar re-verificación si tu perfil fue rechazado",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar cooldown
        if provider_profile.rejected_at:
            from django.conf import settings
            cooldown_hours = settings.PROVIDER_VERIFICATION_CONFIG['reverification_cooldown_hours']
            elapsed = timezone.now() - provider_profile.rejected_at
            
            if elapsed < timezone.timedelta(hours=cooldown_hours):
                remaining_seconds = (cooldown_hours * 3600) - elapsed.total_seconds()
                return error_response(
                    f"Debes esperar {int(remaining_seconds / 60)} minutos antes de solicitar re-verificación",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS
                )
        
        # Validar intentos máximos
        from django.conf import settings
        max_attempts = settings.PROVIDER_VERIFICATION_CONFIG['max_verification_attempts']
        if provider_profile.verification_attempts >= max_attempts:
            return error_response(
                "Has alcanzado el límite máximo de intentos de verificación",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado a resubmitted
        provider_profile.status = 'resubmitted'
        provider_profile.resubmitted_at = timezone.now()
        provider_profile.save()
        
        # Triggear validación
        from apps.core.verification import trigger_validation_if_eligible
        trigger_validation_if_eligible(request.user)
        
        return success_response(
            data={
                'status': 'pending',
                'remaining_attempts': max_attempts - provider_profile.verification_attempts
            },
            message="Solicitud de re-verificación enviada. Tu perfil está en revisión."
        )
