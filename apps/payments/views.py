# ============================================
# PAYMENTS APP - CONSOLIDATED PAYMENT VIEWS
# ============================================

import logging
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

# REST Framework
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.permissions import IsAuthenticated

# Models
from apps.core.models import (
    Booking, Payment, PaymentProof, PaymentMethod,
    BankAccount, Notification, AuditLog, User
)

from apps.core.image_upload import upload_payment_proof

from .payphone import PayPhoneService

logger = logging.getLogger(__name__)


# ============================================
# REST API VIEWS (Existing - Kept)
# ============================================

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
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        
        booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
        
        if booking.payment_status == 'paid':
            return Response(
                {'error': 'Esta reserva ya está pagada'},
                status=drf_status.HTTP_400_BAD_REQUEST
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
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
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
                status=drf_status.HTTP_400_BAD_REQUEST
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
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
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
                status=drf_status.HTTP_400_BAD_REQUEST
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


# ============================================
# TEMPLATE VIEWS (New - From frontend)
# ============================================

@login_required
def payment_process(request, booking_id):
    """
    Vista principal del proceso de pago v2
    Permite al usuario elegir entre PayPhone o Transferencia Bancaria
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    # Verificar que la reserva esté en estado correcto para pagar
    if booking.status not in ['pending', 'accepted']:
        messages.error(request, 'Esta reserva no puede ser pagada en este momento.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Verificar si ya existe un pago
    if booking.payment_status == 'paid':
        messages.info(request, 'Esta reserva ya ha sido pagada.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Calculo de valores e impuestos
    amount_with_tax = booking.sub_total_cost * 100
    service = booking.service * 100
    tax = booking.tax
    amount_without_tax = booking.travel_cost * 100
    
    amount = amount_with_tax + amount_without_tax + tax + service

    context = {
        'booking': booking,
        'amount_with_tax': amount_with_tax,
        'amount_without_tax': amount_without_tax,
        'service': service,
        'tax': tax,
        'amount': amount,
        'payphone_enabled': True,
        'bank_transfer_enabled': True,
        'PAYPHONE_API_TOKEN': settings.PAYPHONE_API_TOKEN,
        'PAYPHONE_STORE_ID': settings.PAYPHONE_STORE_ID,
    }
    
    return render(request, 'payments/process.html', context)


@login_required
def payment_bank_transfer(request, booking_id):
    """
    Vista COMPLETA para procesar pagos por transferencia bancaria
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    # Verificar que la reserva no esté ya pagada
    if booking.payment_status == 'paid':
        messages.info(request, 'Esta reserva ya ha sido pagada.')
        return redirect('booking_detail', booking_id=booking.id)
    
    # Obtener cuentas bancarias activas
    bank_accounts = BankAccount.objects.filter(is_active=True).order_by('display_order')
    
    if request.method == 'POST':
        reference_code = request.POST.get('reference_code', '').strip()
        bank_account_id = request.POST.get('bank_account_id')
        proof_image = request.FILES.get('proof_image')
        
        # Validaciones
        if not bank_account_id:
            messages.error(request, 'Debes seleccionar una cuenta bancaria.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        bank_account = get_object_or_404(BankAccount, id=bank_account_id, is_active=True)
        
        if not reference_code:
            messages.error(request, 'El número de comprobante/referencia es obligatorio.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        if not proof_image:
            messages.error(request, 'Debes subir una imagen del comprobante de pago.')
            return render(request, 'payments/bank_transfer.html', {
                'booking': booking,
                'bank_accounts': bank_accounts,
            })
        
        try:
            # Obtener o crear método de pago
            payment_method, created = PaymentMethod.objects.get_or_create(
                code='bank_transfer',
                defaults={
                    'name': 'Transferencia Bancaria',
                    'description': 'Pago mediante transferencia bancaria',
                    'is_active': True,
                    'requires_proof': True,
                    'requires_reference': True,
                    'display_order': 2,
                    'icon': '🏦'
                }
            )
            
            # Subir comprobante
            proof_url = upload_payment_proof(
                file=proof_image,
                booking_id=str(booking.id)
            )
            
            # Crear registro de comprobante
            payment_proof = PaymentProof.objects.create(
                booking=booking,
                payment_method=payment_method,
                bank_account=bank_account,
                reference_code=reference_code,
                proof_image=proof_url,
                verified=False
            )
            
            # Actualizar estado de la reserva
            booking.payment_status = 'pending_validation'
            booking.save()
            
            # Log de auditoría
            AuditLog.objects.create(
                user=request.user,
                action='Comprobante de transferencia bancaria enviado',
                metadata={
                    'booking_id': str(booking.id),
                    'payment_proof_id': payment_proof.id,
                    'reference_code': reference_code,
                    'bank_account': bank_account.bank_name
                }
            )
            
            # 🔥 NOTIFICACIONES - USANDO TAREAS CELERY
            
            # 1. Email al CLIENTE
            try:
                from core.tasks import send_payment_proof_received_task
                send_payment_proof_received_task.delay(
                    booking_id=str(booking.id),
                    customer_email=booking.customer.email,
                    customer_name=booking.customer.get_full_name() or booking.customer.username,
                    amount=str(booking.total_cost)
                )
            except Exception as e:
                logger.warning(f"Error enviando email al cliente: {e}")
            
            # 2. Email a ADMINS
            try:
                from core.tasks import notify_admin_payment_pending_task
                admin_users = User.objects.filter(is_staff=True, is_active=True)
                admin_emails = [admin.email for admin in admin_users if admin.email]
                
                if admin_emails:
                    notify_admin_payment_pending_task.delay(
                        booking_id=str(booking.id),
                        customer_name=booking.customer.get_full_name() or booking.customer.username,
                        amount=str(booking.total_cost),
                        admin_email_list=admin_emails
                    )
            except Exception as e:
                logger.warning(f"Error enviando notificación a admins: {e}")
            
            # 3. Notificación en el CENTRO (modelo Notification)
            Notification.objects.create(
                user=booking.customer,
                notification_type='payment_received',
                title='💳 Comprobante de Pago Recibido',
                message=f'Hemos recibido tu comprobante de transferencia bancaria. Nuestro equipo lo está validando.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            Notification.objects.create(
                user=booking.provider,
                notification_type='payment_received',
                title='💳 Comprobante de Pago Pendiente',
                message=f'El cliente {booking.customer.get_full_name()} ha enviado un comprobante de pago. Pendiente de validación.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            messages.success(
                request,
                '✅ Comprobante recibido. Nuestro equipo lo verificará pronto. '
                'Recibirás una notificación cuando esté confirmado.'
            )
            return redirect('payment_confirmation', payment_id=payment_proof.id)
            
        except Exception as e:
            logger.error(f"Error en payment_bank_transfer: {e}")
            messages.error(request, f'Error al subir comprobante: {str(e)}')
    
    return render(request, 'payments/bank_transfer.html', {
        'booking': booking,
        'bank_accounts': bank_accounts,
    })


@login_required
def payment_confirmation(request, payment_id):
    """
    Vista de confirmación después de registrar un pago
    Funciona con PaymentProof o Payment
    """
    # Intenta obtener como PaymentProof primero
    payment_proof = get_object_or_404(PaymentProof, id=payment_id)
    booking = payment_proof.booking
    
    # Verificar que el usuario sea el cliente
    if booking.customer != request.user:
        messages.error(request, 'No tienes acceso a este recurso.')
        return redirect('home')
    
    context = {
        'payment_proof': payment_proof,
        'booking': booking,
        'payment': payment_proof,  # Para compatibilidad con template
    }
    
    return render(request, 'payments/payment_confirmation.html', context)


@login_required
def confirm_bank_transfer_payment(request, booking_id):
    """
    Vista simplificada para confirmar que se realizó la transferencia
    (Sin necesidad de subir comprobante en esta versión simplificada)
    """
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    if request.method == 'POST':
        # Crear el registro de pago pendiente
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_cost,
            payment_method='bank_transfer',
            status='pending_validation',
            transaction_id=f"BT-{booking.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            notes=request.POST.get('notes', ''),
        )
        
        # Actualizar el estado de pago de la reserva
        booking.payment_status = 'pending_validation'
        booking.save()
        
        # Enviar notificaciones
        notify_admin_pending_payment(payment)
        send_payment_confirmation_email(booking, payment)
        
        messages.success(
            request, 
            '¡Gracias por tu pago! Nuestro equipo lo está validando. '
            'Recibirás pronto una notificación de que ha sido procesado.'
        )
        
        return redirect('booking_detail', booking_id=booking.id)
    
    return redirect('payment_bank_transfer', booking_id=booking_id)


# ============================================
# WEBHOOKS
# ============================================

@csrf_exempt
def payphone_callback(request):
    """
    Callback de PayPhone - Redirige al usuario después del pago
    """
    logger.info("="*50)
    logger.info("INICIANDO PAYPHONE CALLBACK")
    logger.info("="*50)
    logger.info(f"GET params: {request.GET}")
    logger.info(f"POST params: {request.POST}")
    
    transaction_id = request.GET.get('id')
    client_transaction_id = request.GET.get('clientTransactionId')
    
    logger.info(f"PayPhone callback - ID: {transaction_id}, ClientTxId: {client_transaction_id}")
    
    # Validar parámetros
    if not transaction_id or not client_transaction_id:
        logger.error("Faltan parámetros en callback")
        messages.error(request, 'Error: Faltan parámetros de pago')
        return redirect('home')

    # Buscar booking
    try:
        booking = Booking.objects.get(id=client_transaction_id)
        logger.info(f"Booking encontrado: {booking.id}")
    except Booking.DoesNotExist:
        logger.error(f"Booking no encontrado: {client_transaction_id}")
        messages.error(request, 'Reserva no encontrada')
        return redirect('home')

    # Confirmar con PayPhone
    headers = {
        'Authorization': f'Bearer {settings.PAYPHONE_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    
    confirm_url = settings.PAYPHONE_URL_CONFIRM_PAYPHONE

    try:
        response = requests.post(
            confirm_url,
            headers=headers,
            json={
                'id': int(transaction_id),
                'clientTxId': str(client_transaction_id)
            },
            timeout=15
        )
        
        logger.info(f"PayPhone status: {response.status_code}")
        logger.info(f"PayPhone response: {response.text}")
        
        response.raise_for_status()
        transaction_data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error confirmando PayPhone: {e}")
        logger.error(f"Response: {getattr(e.response, 'text', 'No response')}")
        messages.error(request, 'Error al verificar el pago. Contacta a soporte.')
        return redirect('booking_detail', booking_id=booking.id)

    # Procesar según estado
    transaction_status = transaction_data.get('transactionStatus', 'Unknown')
    logger.info(f"Transaction status: {transaction_status}")
    
    if transaction_status == 'Approved':
        try:
            with transaction.atomic():
                # Verificar si ya está pagado
                if booking.payment_status != 'paid':
                    # Crear registro de pago
                    payment = Payment.objects.create(
                        booking=booking,
                        amount=booking.total_cost,
                        payment_method='payphone',
                        status='completed',
                        transaction_id=transaction_id
                    )
                    logger.info(f"Pago creado: {payment.id}")
                    
                    # Actualizar booking
                    booking.payment_status = 'paid'
                    booking.save()
                    logger.info(f"Booking actualizado a paid: {booking.id}")
                    
                    # Crear notificaciones (Manejado por Signals)
                    logger.info("Notificaciones delegadas a signals")

                    
                    messages.success(request, '¡Pago confirmado exitosamente! Tu reserva está activa.')
                else:
                    logger.info(f"Booking ya estaba pagado: {booking.id}")
                    messages.info(request, 'Este pago ya había sido procesado anteriormente.')
                    
        except Exception as e:
            logger.error(f"Error procesando pago aprobado: {e}", exc_info=True)
            messages.error(request, f"Error al procesar el pago. Contacta a soporte: {e}")
            return redirect('booking_detail', booking_id=booking.id)
            
        return redirect('booking_detail', booking_id=booking.id)
    
    else:
        logger.warning(f"Pago no aprobado. Estado: {transaction_status}")
        messages.warning(request, f'El pago no fue aprobado. Estado: {transaction_status}')
        return redirect('booking_detail', booking_id=booking.id)


# ============================================
# HELPER FUNCTIONS
# ============================================

def notify_admin_pending_payment(payment):
    """
    Envía notificación a los administradores sobre un pago pendiente de validación
    """
    # Obtener todos los administradores
    admins = User.objects.filter(is_staff=True, is_active=True)
    
    admin_emails = [admin.email for admin in admins if admin.email]
    
    if admin_emails:
        subject = f'[Liberi] Nuevo pago por validar - Reserva #{payment.booking.id}'
        message = f"""
        Hola Administrador,
        
        Se ha registrado un nuevo pago por transferencia bancaria que requiere validación:
        
        DETALLES DEL PAGO:
        - ID de Pago: {payment.id}
        - ID de Reserva: {payment.booking.id}
        - Cliente: {payment.booking.customer.get_full_name() or payment.booking.customer.username}
        - Monto: ${payment.amount}
        - Número de Referencia: {payment.reference_number or 'N/A'}
        - Fecha de Transferencia: {payment.transfer_date or 'N/A'}
        
        Por favor, revisa el comprobante y valida el pago en el panel de administración:
        {settings.BASE_DIR}/admin/bookings/payment/{payment.id}/change/
        
        ---
        Sistema Liberi
        """
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Error enviando email a administradores: {e}")


def send_payment_confirmation_email(booking, payment):
    """
    Envía email de confirmación al cliente
    """
    subject = f'Confirmación de Pago - Reserva #{booking.id}'
    message = f"""
    Hola {booking.customer.get_full_name() or booking.customer.username},
    
    Hemos recibido tu comprobante de pago por transferencia bancaria.
    
    DETALLES DE TU RESERVA:
    - Número de Reserva: #{booking.id}
    - Servicio: {booking.get_services_display()}
    - Monto Total: ${booking.total_cost}
    - Fecha Programada: {booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
    
    ESTADO DEL PAGO:
    Tu pago está siendo validado por nuestro equipo. Este proceso generalmente toma entre 1-4 horas hábiles.
    Te notificaremos por email tan pronto como tu pago sea confirmado.
    
    ¿Tienes preguntas? Contáctanos en soporte@liberi.com
    
    ¡Gracias por confiar en Liberi!
    
    ---
    El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.customer.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Error enviando email de confirmación: {e}")


def confirm_payphone_transaction(transaction_id, client_transaction_id):
    """
    Confirma una transacción con PayPhone
    Retorna: (success_request, success_transaction, payload)
    """
    try:
        headers = {
            'Authorization': f'Bearer {settings.PAYPHONE_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'id': int(transaction_id),
            'clientTxId': client_transaction_id
        }
        
        logger.info(f'Enviando confirmación a {settings.PAYPHONE_URL_CONFIRM_PAYPHONE}')
        logger.info(f'Headers: {headers}')
        logger.info(f'Payload: {payload}')
        
        response = requests.post(
            settings.PAYPHONE_URL_CONFIRM_PAYPHONE,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        logger.info(f'Status Code: {response.status_code}')
        logger.info(f'Response Text: {response.text}')
        
        response.raise_for_status()
        
        data = response.json()
        logger.info(f'Parsed Response: {data}')
        
        # Verificar el estado de la transacción
        success_request = response.status_code == 200
        
        # PayPhone retorna transactionStatus con valores como "Approved", "Rejected", etc
        transaction_status = data.get('transactionStatus') or data.get('status')
        success_transaction = transaction_status == 'Approved'
        
        return success_request, success_transaction, data
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Error en confirm_payphone_transaction: {e}')
        return False, False, {'error': str(e)}
