from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import json
from .models import AuditLog
from .verification import validate_provider_profile
from .tasks import send_provider_approval_notification_task  # Assuming this exists or will be used
from apps.core.email_utils import run_task

@login_required
def request_reverification(request):
    """
    Vista para que el proveedor solicite nueva verificación
    después de corregir su perfil.
    """
    if request.user.profile.role != 'provider':
        messages.error(request, 'Solo los proveedores pueden solicitar verificación')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'provider_profile'):
        return redirect('dashboard')
        
    provider_profile = request.user.provider_profile
    
    # Verificar si puede re-solicitar
    can_request, error_message = can_request_reverification(provider_profile)
    
    if not can_request:
        messages.error(request, error_message)
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Actualizar estado
        provider_profile.status = 'resubmitted'
        provider_profile.verification_attempts += 1
        provider_profile.resubmitted_at = timezone.now()
        provider_profile.save()
        
        # Disparar validación automática (síncrona por ahora, idealmente async)
        is_approved, rejections, warnings = validate_provider_profile(provider_profile)
        
        if is_approved:
            provider_profile.status = 'approved'
            provider_profile.save()
            
            # Notificar aprobación
            from .tasks import send_provider_approval_confirmed_task
            run_task(
                send_provider_approval_confirmed_task,
                provider_email=request.user.email,
                provider_name=request.user.get_full_name()
            )
            
            messages.success(request, '¡Tu perfil ha sido verificado y aprobado exitosamente!')
        elif rejections:
            provider_profile.status = 'rejected'
            provider_profile.rejection_reasons = json.dumps(rejections)
            provider_profile.rejected_at = timezone.now()
            provider_profile.save()
            
            # Notificar rechazo
            from .tasks import send_provider_rejection_notification_task
            run_task(
                send_provider_rejection_notification_task,
                provider_email=request.user.email,
                provider_name=request.user.get_full_name(),
                rejection_reasons=rejections
            )
            
            messages.warning(request, 'Tu perfil fue revisado pero aún tiene problemas. Por favor revisa los motivos.')
        
        AuditLog.objects.create(
            user=request.user,
            action='Re-solicitud de verificación',
            metadata={
                'attempt_number': provider_profile.verification_attempts,
                'result': provider_profile.status
            }
        )
        
        return redirect('dashboard')
    
    # GET: Mostrar página con motivos de rechazo y botón
    rejection_reasons = []
    if provider_profile.rejection_reasons:
        try:
            rejection_reasons = json.loads(provider_profile.rejection_reasons)
        except:
            pass
            
    context = {
        'provider_profile': provider_profile,
        'rejection_reasons': rejection_reasons,
    }
    return render(request, 'providers/request_reverification.html', context)

def can_request_reverification(provider_profile):
    """Verifica si el proveedor puede solicitar nueva verificación"""
    from datetime import timedelta
    from django.conf import settings
    
    # Solo perfiles rechazados pueden re-solicitar
    if provider_profile.status != 'rejected':
        return False, "Tu perfil no está en estado rechazado"
    
    # Cooldown
    if provider_profile.rejected_at:
        config = settings.PROVIDER_VERIFICATION_CONFIG
        cooldown_hours = config.get('reverification_cooldown_hours', 1)
        cooldown = timedelta(hours=cooldown_hours)
        
        time_since_rejection = timezone.now() - provider_profile.rejected_at
        
        if time_since_rejection < cooldown:
            remaining = cooldown - time_since_rejection
            minutes = max(1, int(remaining.total_seconds() / 60))  # Mínimo 1 minuto
            return False, f"Debes esperar {minutes} minutos antes de solicitar nueva verificación"
    
    # Límite de re-intentos
    config = settings.PROVIDER_VERIFICATION_CONFIG
    max_attempts = config.get('max_verification_attempts', 5)
    
    if provider_profile.verification_attempts >= max_attempts:
        return False, "Has alcanzado el límite de intentos de verificación. Por favor, contacta a soporte."
    
    return True, None
