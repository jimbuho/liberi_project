from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from core.models import User, Service, Booking, Payment, WithdrawalRequest, ProviderProfile, Notification

import logging

logger = logging.getLogger(__name__)

# ============================================
# EMAIL DE VERIFICACIÓN
# ============================================

@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, user_id, user_email, verification_url, user_name):
    """
    Tarea asíncrona para enviar email de verificación
    
    Args:
        user_id: ID del usuario
        user_email: Email del destinatario
        verification_url: URL completa de verificación
        user_name: Nombre completo del usuario
    """
    try:
        logger.info(f"📧 Iniciando envío de email de verificación a {user_email}")
        
        # Renderizar templates
        html_content = render_to_string('emails/verification_email.html', {
            'user_name': user_name,
            'verification_url': verification_url,
            'site_name': 'Liberi',
            'support_email': settings.DEFAULT_FROM_EMAIL
        })
        
        text_content = render_to_string('emails/verification_email.txt', {
            'user_name': user_name,
            'verification_url': verification_url,
            'site_name': 'Liberi'
        })
        
        # Crear email
        subject = '✓ Verifica tu email - Liberi'
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email]
        )
        email_message.attach_alternative(html_content, "text/html")
        
        # Enviar
        email_message.send(fail_silently=False)
        
        logger.info(f"✅ Email de verificación enviado exitosamente a {user_email}")
        return {'success': True, 'email': user_email}
        
    except Exception as e:
        logger.error(f"❌ Error enviando email de verificación a {user_email}: {e}", exc_info=True)
        # Retry automático con backoff exponencial
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# ============================================
# EMAIL DE BIENVENIDA
# ============================================

@shared_task(bind=True, max_retries=3)
def send_welcome_email_task(self, user_id, user_email, user_name, is_provider=False):
    """
    Tarea asíncrona para enviar email de bienvenida
    
    Args:
        user_id: ID del usuario
        user_email: Email del destinatario
        user_name: Nombre completo del usuario
        is_provider: True si es proveedor, False si es cliente
    """
    try:
        logger.info(f"📧 Iniciando envío de email de bienvenida a {user_email} (provider={is_provider})")
        
        # Determinar template según rol
        template = 'emails/welcome_provider.html' if is_provider else 'emails/welcome_customer.html'
        text_template = 'emails/welcome_provider.txt' if is_provider else 'emails/welcome_customer.txt'
        
        # Contexto
        context = {
            'user_name': user_name,
            'site_name': 'Liberi',
            'site_url': settings.BASE_URL,
            'login_url': f"{settings.BASE_URL}/login/",
            'dashboard_url': f"{settings.BASE_URL}/dashboard/",
            'is_provider': is_provider
        }
        
        # Renderizar
        html_content = render_to_string(template, context)
        text_content = render_to_string(text_template, context)
        
        # Enviar
        subject = '🎉 ¡Bienvenido a Liberi!' if not is_provider else '🎉 ¡Bienvenido a Liberi - Panel de Proveedor!'
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)
        
        logger.info(f"✅ Email de bienvenida enviado exitosamente a {user_email}")
        return {'success': True, 'email': user_email}
        
    except Exception as e:
        logger.error(f"❌ Error enviando email de bienvenida a {user_email}: {e}", exc_info=True)
        # Retry automático con backoff exponencial
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# ============================================
# NOTIFICACIONES DE PROVEEDOR
# ============================================

@shared_task
def send_provider_approval_notification_task(provider_id, admin_emails):
    """Notifica a admins cuando proveedor completa primer servicio"""
    
    
    try:
        provider = User.objects.get(id=provider_id)
        provider_profile = provider.provider_profile
        service = Service.objects.filter(provider=provider).first()
        
        subject = f'🆕 Nueva Solicitud de Aprobación de Proveedor - {provider_profile.get_display_name()}'
        message = f"""
Hola Equipo Administrativo,

Un nuevo proveedor ha completado el requisito y solicita aprobación de su perfil.

INFORMACIÓN DEL PROVEEDOR:
- Nombre: {provider.get_full_name()}
- Nombre Comercial: {provider_profile.business_name or 'No especificado'}
- Email: {provider.email}
- Categoría: {provider_profile.category.name}
- Descripción: {provider_profile.description[:200]}...

PRIMER SERVICIO CREADO:
- Nombre: {service.name if service else 'N/A'}
- Precio: ${service.base_price if service else 'N/A'}
- Duración: {service.duration_minutes if service else 'N/A'} minutos

ACCIÓN REQUERIDA:
Revisa el perfil del proveedor en el panel administrativo y aprueba o rechaza su solicitud.

Link directo: {settings.BASE_URL}/admin/core/providerprofile/{provider.id}/change/

---
Sistema Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )
        logger.info(f"✅ Notificación de nuevo proveedor enviada a admins")
    except Exception as e:
        logger.error(f"❌ Error enviando notificación de nuevo proveedor: {e}")
        raise


@shared_task
def send_provider_approval_confirmed_task(provider_email, provider_name):
    """Notifica al proveedor que su perfil fue aprobado"""
    subject = f'✅ Tu Perfil Ha Sido Aprobado - Liberi'
    message = f"""
Hola {provider_name},

¡Excelentes noticias! Tu perfil ha sido revisado y aprobado exitosamente.

Tu cuenta está activa y ahora puedes:
- Recibir reservas de clientes
- Ver tus ganancias en tiempo real
- Solicitar retiros de tu dinero
- Gestionar tus horarios y cobertura

Accede a tu panel: {settings.BASE_URL}/dashboard/

Si tienes preguntas, contacta a: soporte@liberi.com

¡Bienvenido a Liberi!

---
El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider_email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de aprobación enviado a {provider_email}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de aprobación: {e}")
        raise


# ============================================
# NOTIFICACIONES DE RESERVAS
# ============================================

@shared_task
def send_new_booking_to_provider_task(booking_id):
    """Notifica al proveedor sobre una nueva reserva"""
    try:
        booking = Booking.objects.get(id=booking_id)
        provider = booking.provider
        
        subject = f'📋 Nueva Reserva - {booking.customer.get_full_name()}'
        message = f"""
Hola {provider.get_full_name() or provider.username},

¡Una nueva reserva ha llegado!

DETALLES:
- Cliente: {booking.customer.get_full_name() or booking.customer.username}
- Teléfono: {booking.customer.profile.phone if hasattr(booking.customer, 'profile') else 'No disponible'}
- Servicio: {booking.get_services_display()}
- Fecha: {booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M")}
- Ubicación: {booking.location.address if booking.location else 'Por confirmar'}
- Zona: {booking.location.zone.name if booking.location and booking.location.zone else 'N/A'}
- Monto: ${booking.total_cost}

Accede a tu panel para aceptar o rechazar esta reserva: {settings.BASE_URL}/bookings/{booking.id}/

---
Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider.email],
            fail_silently=False,
        )
        logger.info(f"✅ Notificación de nueva reserva enviada a {provider.email}")
    except Exception as e:
        logger.error(f"❌ Error enviando notificación de reserva: {e}")
        raise


@shared_task
def send_booking_accepted_to_customer_task(booking_id):
    """Notifica al cliente cuando proveedor acepta reserva"""
    
    try:
        booking = Booking.objects.get(id=booking_id)
        customer = booking.customer
        
        subject = f'✅ Tu Reserva Ha Sido Aceptada'
        message = f"""
Hola {customer.get_full_name() or customer.username},

¡Excelentes noticias! Tu reserva ha sido aceptada.

DETALLES DE TU RESERVA:
- Proveedor: {booking.provider.get_full_name() or booking.provider.username}
- Teléfono: {booking.provider.profile.phone if hasattr(booking.provider, 'profile') else 'No disponible'}
- Servicio(s): {booking.get_services_display()}
- Fecha: {booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M")}
- Ubicación: {booking.location.address if booking.location else 'Por confirmar'}
- Monto Total: ${booking.total_cost}

PRÓXIMO PASO:
Completa el pago para confirmar definitivamente tu reserva. 
El proveedor está esperando la confirmación del pago.

Accede a tu reserva en: {settings.BASE_URL}/bookings/{booking.id}/

¡Gracias por confiar en Liberi!

---
El Equipo de Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de reserva aceptada enviado a {customer.email}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de reserva aceptada: {e}")
        raise


# ============================================
# NOTIFICACIONES DE PAGO
# ============================================

@shared_task
def send_payment_approved_to_customer_task(payment_id):
    """Notifica al cliente cuando pago es aprobado"""
    
    try:
        payment = Payment.objects.get(id=payment_id)
        booking = payment.booking
        customer = booking.customer
        
        subject = f'✅ Pago Aprobado - Reserva #{str(booking.id)[:8]}'
        message = f"""
Hola {customer.get_full_name() or customer.username},

¡Excelentes noticias! Tu pago ha sido validado y aprobado exitosamente.

═══════════════════════════════════════
📋 DETALLES DE TU RESERVA
═══════════════════════════════════════

- Número de Reserva: #{str(booking.id)[:8]}
- Servicio(s): {booking.get_services_display()}
- Monto Pagado: ${payment.amount} USD
- Fecha Programada: {booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M")}
- Proveedor: {booking.provider.get_full_name() or booking.provider.username}

═══════════════════════════════════════

✅ Tu reserva está CONFIRMADA
El proveedor ha sido notificado y se pondrá en contacto contigo próximamente para coordinar los detalles finales.

Si tienes alguna pregunta, no dudes en contactarnos.

¡Gracias por confiar en Liberi! 💙

---
El Equipo de Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de pago aprobado enviado a cliente")
    except Exception as e:
        logger.error(f"❌ Error enviando email de pago aprobado: {e}")
        raise


@shared_task
def send_payment_approved_to_provider_task(payment_id):
    """Notifica al proveedor cuando pago del cliente es aprobado"""

    try:
        payment = Payment.objects.get(id=payment_id)
        booking = payment.booking
        provider = booking.provider
        
        subject = f'💰 Pago Confirmado - Reserva #{str(booking.id)[:8]}'
        message = f"""
Hola {provider.get_full_name() or provider.username},

¡Buenas noticias! El pago de tu cliente ha sido verificado y confirmado.

═══════════════════════════════════════
📋 DETALLES DE LA RESERVA
═══════════════════════════════════════

- Número de Reserva: #{str(booking.id)[:8]}
- Cliente: {booking.customer.get_full_name() or booking.customer.username}
- Teléfono del Cliente: {booking.customer.profile.phone if hasattr(booking.customer, 'profile') else 'No disponible'}
- Servicio(s): {booking.get_services_display()}
- Monto Pagado: ${payment.amount} USD
- Fecha Programada: {booking.scheduled_time.strftime("%d de %B del %Y a las %H:%M")}
- Dirección: {booking.location.address if booking.location else 'Por confirmar'}

═══════════════════════════════════════

✅ PRÓXIMOS PASOS:
1. Revisa los detalles de la reserva
2. Contacta al cliente para confirmar la hora exacta
3. Prepara todo lo necesario para el servicio
4. Acude puntualmente a la cita

El cliente está esperando tu confirmación. Por favor, ponte en contacto lo antes posible.

¡Éxito con tu servicio! 💪

---
El Equipo de Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider.email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de pago aprobado enviado a proveedor")
    except Exception as e:
        logger.error(f"❌ Error enviando email de pago aprobado a proveedor: {e}")
        raise


@shared_task(bind=True, max_retries=2)
def send_payment_proof_received_task(self, booking_id, customer_email, customer_name, amount):
    """Notifica al cliente que su comprobante fue recibido"""
    try:
        subject = f'Comprobante de Pago Recibido - Reserva #{booking_id}'
        message = f"""
Hola {customer_name},

Hemos recibido tu comprobante de pago por transferencia bancaria.

DETALLES:
- Reserva: #{booking_id}
- Monto: ${amount}
- Estado: Pendiente de validación

Nuestro equipo lo está verificando. Este proceso generalmente toma entre 1-4 horas hábiles.
Te notificaremos por email tan pronto como tu pago sea confirmado.

¡Gracias por confiar en Liberi!

---
El Equipo de Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de comprobante recibido enviado a {customer_email}")
        
    except Exception as exc:
        logger.error(f"❌ Error en send_payment_proof_received_task: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================
# NOTIFICACIONES DE RETIROS
# ============================================

@shared_task
def send_withdrawal_request_to_admins_task(withdrawal_id):
    """Notifica a admins sobre nueva solicitud de retiro"""
    
    try:
        withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        admin_emails = [admin.email for admin in admin_users if admin.email]
        
        if not admin_emails:
            logger.warning("No hay emails de admin configurados")
            return
        
        subject = f'💰 Nueva Solicitud de Retiro - {withdrawal.provider.get_full_name()}'
        message = f"""
Nuevo retiro solicitado:

DETALLES:
- Proveedor: {withdrawal.provider.get_full_name()}
- Email: {withdrawal.provider.email}
- Monto Solicitado: ${withdrawal.requested_amount}
- Comisión ({withdrawal.commission_percent}%): ${withdrawal.commission_amount}
- A Pagar: ${withdrawal.amount_payable}
- Banco: {withdrawal.provider_bank_account.bank.name if withdrawal.provider_bank_account else 'N/A'}
- Cuenta: {withdrawal.provider_bank_account.account_number_masked if withdrawal.provider_bank_account else 'N/A'}

ACCIÓN REQUERIDA:
Revisa y procesa el retiro en el panel administrativo.

Link directo: {settings.BASE_URL}/admin/core/withdrawalrequest/{withdrawal.id}/change/

---
Sistema Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )
        logger.info(f"✅ Notificación de retiro enviada a admins")
    except Exception as e:
        logger.error(f"❌ Error enviando notificación de retiro: {e}")
        raise


@shared_task
def send_withdrawal_completed_to_provider_task(withdrawal_id):
    """Notifica al proveedor cuando su retiro fue completado"""
    
    try:
        withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
        provider = withdrawal.provider
        
        subject = f'💰 Retiro Completado - ${withdrawal.amount_payable}'
        message = f"""
Hola {provider.get_full_name() or provider.username},

¡Excelentes noticias! Tu solicitud de retiro ha sido procesada y completada exitosamente.

═══════════════════════════════════════
DETALLES DEL RETIRO
═══════════════════════════════════════

- Monto Solicitado: ${withdrawal.requested_amount}
- Comisión ({withdrawal.commission_percent}%): ${withdrawal.commission_amount}
- Monto a Pagar: ${withdrawal.amount_payable}
- Banco: {withdrawal.provider_bank_account.bank.name if withdrawal.provider_bank_account else 'N/A'}
- Cuenta: {withdrawal.provider_bank_account.account_number_masked if withdrawal.provider_bank_account else 'N/A'}
- Número de Comprobante: {withdrawal.transfer_receipt_number or 'N/A'}
- Fecha de Procesamiento: {withdrawal.updated_at.strftime("%d de %B del %Y a las %H:%M") if withdrawal.updated_at else 'N/A'}

═══════════════════════════════════════

El dinero ha sido transferido a tu cuenta bancaria. Según tu banco, puede tardar entre 1-3 días hábiles en aparecer en tu cuenta.

Si tienes preguntas o no recibiste el dinero en 3 días, por favor contacta a nuestro equipo de soporte.

¡Gracias por confiar en Liberi! 💙

---
El Equipo de Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider.email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de retiro completado enviado a {provider.email}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de retiro completado: {e}")
        raise

# ============================================
# NOTIFICACIONES DE PAGOS
# ============================================

@shared_task
def send_payment_confirmed_to_customer_task(booking_id, customer_email, customer_name, amount, provider_name):
    """Notifica al cliente que su pago fue confirmado"""
    subject = '✅ Pago Confirmado - Liberi'
    message = f"""
Hola {customer_name},

¡Tu pago ha sido confirmado exitosamente!

DETALLES DEL PAGO:
- Monto: ${amount}
- Proveedor: {provider_name}
- Método: PayPhone
- Estado: Confirmado

Tu reserva está activa y el proveedor ha sido notificado.

Puedes ver los detalles de tu reserva en: {settings.BASE_URL}/bookings/{booking_id}/

¡Gracias por usar Liberi!

---
El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de confirmación de pago enviado a {customer_email}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de confirmación de pago: {e}")
        raise


@shared_task
def send_payment_received_to_provider_task(booking_id, provider_email, provider_name, amount, customer_name):
    """Notifica al proveedor que ha recibido un pago"""
    subject = '💰 Pago Recibido - Liberi'
    message = f"""
Hola {provider_name},

¡Has recibido un nuevo pago!

DETALLES DEL PAGO:
- Monto: ${amount}
- Cliente: {customer_name}
- Método: PayPhone
- Estado: Confirmado

El dinero está disponible en tu balance y podrás retirarlo una vez completado el servicio.

Ver detalles de la reserva: {settings.BASE_URL}/bookings/{booking_id}/

---
El Equipo de Liberi
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[provider_email],
            fail_silently=False,
        )
        logger.info(f"✅ Email de pago recibido enviado a {provider_email}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de pago recibido: {e}")
        raise

@shared_task
def send_provider_approval_email_task(provider_profile_id):
    """
    Envía email de bienvenida cuando un proveedor es aprobado
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        provider_profile = ProviderProfile.objects.select_related('user').get(pk=provider_profile_id)
        provider = provider_profile.user
        
        # Contexto para el template
        context = {
            'provider_name': provider.get_full_name() or provider.username,
            'business_name': provider_profile.business_name or 'tu negocio',
            'category': provider_profile.category.name,
            'site_name': 'Liberi',
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'coverage_url': f"{settings.SITE_URL}/provider/coverage/",
            'zone_costs_url': f"{settings.SITE_URL}/provider/zone-costs/",
            'schedule_url': f"{settings.SITE_URL}/provider/schedule/",
        }
        
        # Subject
        subject = f'¡Felicitaciones! Tu perfil de proveedor ha sido aprobado - Liberi'
        
        # Renderizar templates HTML y texto plano
        html_content = render_to_string('emails/provider_approval.html', context)
        text_content = render_to_string('emails/provider_approval.txt', context)
        
        # Crear email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[provider.email]
        )
        
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f'✅ Email de aprobación enviado a {provider.email}')
        return True
        
    except ProviderProfile.DoesNotExist:
        logger.error(f'❌ ProviderProfile {provider_profile_id} no existe')
        return False
    except Exception as e:
        logger.error(f'❌ Error enviando email de aprobación del proveedor: {e}')
        return False

# ============================================================================
# CORE/TASKS.PY - NUEVAS TAREAS
# Agregar al final del archivo
# ============================================================================

@shared_task
def check_uncompleted_services():
    """
    Tarea periódica (cada hora) que verifica servicios que no se completaron
    y envía notificaciones al cliente preguntando si recibió el servicio
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.contrib.auth.models import User
    
    logger.info("="*50)
    logger.info("Iniciando verificación de servicios no completados")
    logger.info("="*50)
    
    now = timezone.now()
    
    # Buscar servicios que:
    # 1. Están aceptados y pagados
    # 2. La fecha programada ya pasó (más de 2 horas)
    # 3. NO están completados
    # 4. NO tienen incidencia reportada
    
    two_hours_ago = now - timedelta(hours=2)
    
    uncompleted_bookings = Booking.objects.filter(
        status='accepted',
        payment_status='paid',
        scheduled_time__lt=two_hours_ago,
        incident_reported=False
    ).select_related('customer', 'provider')
    
    logger.info(f"Servicios no completados encontrados: {uncompleted_bookings.count()}")
    
    for booking in uncompleted_bookings:
        try:
            # Verificar que no se haya enviado notificación recientemente (últimas 24h)
            recent_notification = Notification.objects.filter(
                user=booking.customer,
                booking=booking,
                notification_type='system',
                title__contains='¿Recibiste el servicio?',
                created_at__gte=now - timedelta(hours=24)
            ).exists()
            
            if recent_notification:
                logger.info(f"Booking {booking.id}: Ya se notificó recientemente")
                continue
            
            # Crear notificación para el cliente
            Notification.objects.create(
                user=booking.customer,
                notification_type='system',
                title='❓ ¿Recibiste el servicio?',
                message=f'Tu cita con {booking.provider.get_full_name()} estaba programada para {booking.scheduled_time.strftime("%d/%m/%Y %H:%M")}. Por favor confirma si recibiste el servicio.',
                booking=booking,
                action_url=f'/bookings/{booking.id}/'
            )
            
            # Enviar email al cliente
            send_service_completion_check_email_task.delay(booking_id=str(booking.id))
            
            logger.info(f"✅ Notificación enviada para booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Error procesando booking {booking.id}: {e}")
    
    logger.info("Verificación completada")
    return f"Procesados {uncompleted_bookings.count()} servicios"


@shared_task
def send_service_completion_check_email_task(booking_id):
    """
    Envía email al cliente preguntando si recibió el servicio
    """
    try:
        booking = Booking.objects.get(id=booking_id)
        customer = booking.customer
        
        subject = f'¿Recibiste tu servicio? - Reserva #{str(booking.id)[:8]}'
        
        message = f"""
Hola {customer.get_full_name() or customer.username},

Notamos que tu servicio con {booking.provider.get_full_name()} estaba programado para {booking.scheduled_time.strftime('%d/%m/%Y a las %H:%M')}.

¿Recibiste el servicio correctamente?

Si TODO ESTÁ BIEN:
- No necesitas hacer nada. El proveedor marcará el servicio como completado.

Si NO RECIBISTE EL SERVICIO o hubo algún problema:
- Ingresa a tu reserva y reporta la incidencia: https://liberi.ec/bookings/{booking.id}/
- Nuestro equipo revisará el caso y te contactará.

DATOS DE TU RESERVA:
- Número de Reserva: #{str(booking.id)[:8]}
- Servicio: {booking.get_services_display()}
- Proveedor: {booking.provider.get_full_name()}
- Monto: ${booking.total_cost}

Si tienes dudas, contáctanos: soporte@liberi.ec

---
Equipo Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=False,
        )
        
        logger.info(f"✅ Email de verificación enviado a {customer.email}")
        return f"Email enviado a {customer.email}"
        
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} no encontrado")
        return f"Error: Booking no encontrado"
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return f"Error: {str(e)}"


@shared_task
def send_incident_notification_to_admins_task(booking_id, admin_emails):
    """
    Notifica a los administradores sobre una incidencia reportada
    """
    try:
        booking = Booking.objects.get(id=booking_id)
        
        subject = f'🚨 INCIDENCIA REPORTADA - Reserva #{str(booking.id)[:8]}'
        
        message = f"""
ALERTA: Un cliente ha reportado una incidencia

DETALLES DE LA RESERVA:
- ID: {booking.id}
- Cliente: {booking.customer.get_full_name()} ({booking.customer.email})
- Proveedor: {booking.provider.get_full_name()} ({booking.provider.email})
- Servicio: {booking.get_services_display()}
- Fecha Programada: {booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
- Monto: ${booking.total_cost}

DESCRIPCIÓN DEL PROBLEMA:
{booking.incident_description}

ACCIÓN REQUERIDA:
1. Revisar el caso en el admin: /admin/core/booking/{booking.id}/change/
2. Contactar al cliente: {booking.customer.email}
3. Contactar al proveedor: {booking.provider.email}
4. Determinar solución (reembolso, reprogramación, etc.)

---
Sistema Liberi
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )
        
        logger.info(f"Email de incidencia enviado a {len(admin_emails)} admins")
        return f"Email enviado"
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {str(e)}"