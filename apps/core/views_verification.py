from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import json
from .models import AuditLog
from apps.core.email_utils import run_task

@login_required
def request_reverification(request):
    """
    Vista para que el proveedor solicite nueva verificación
    después de corregir su perfil.
    
    IMPORTANTE: La validación se ejecuta en SEGUNDO PLANO (Celery)
    para evitar timeouts HTTP 502.
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
        # Actualizar estado a 'resubmitted' (re-enviado)
        provider_profile.status = 'resubmitted'
        provider_profile.verification_attempts += 1
        provider_profile.resubmitted_at = timezone.now()
        provider_profile.save()
        
        # Log de auditoría
        AuditLog.objects.create(
            user=request.user,
            action='Re-solicitud de verificación enviada',
            metadata={
                'attempt_number': provider_profile.verification_attempts,
                'status': 'resubmitted'
            }
        )
        
        # =====================================================
        # DISPARAR VALIDACIÓN EN SEGUNDO PLANO (NO BLOQUEA)
        # =====================================================
        from .tasks import validate_provider_profile_task
        
        # Usar run_task para ejecutar en background (Celery)
        run_task(validate_provider_profile_task, provider_profile.pk)
        
        # Mensaje al usuario - la validación está en proceso
        messages.success(
            request, 
            '✅ Tu solicitud de verificación ha sido enviada. '
            'Este proceso puede tomar unos minutos. '
            'Te notificaremos por correo electrónico cuando tengamos el resultado.'
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