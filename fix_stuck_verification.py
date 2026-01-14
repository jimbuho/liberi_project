"""
Script para desbloquear perfiles de proveedor atascados en estado 'pending' o 'resubmitted'
que no completaron su validación.

Este script debe ejecutarse desde el shell de Django en producción:
fly ssh console -a liberi-app
python manage.py shell < fix_stuck_verification.py
"""

from apps.core.models import ProviderProfile
from django.utils import timezone
import json

print("=" * 60)
print("DESBLOQUEANDO PERFILES ATASCADOS EN VERIFICACIÓN")
print("=" * 60)

# Buscar perfiles que están en 'pending' o 'resubmitted' por más de 5 minutos
from datetime import timedelta
five_minutes_ago = timezone.now() - timedelta(minutes=5)

stuck_profiles = ProviderProfile.objects.filter(
    status__in=['pending', 'resubmitted'],
    updated_at__lt=five_minutes_ago
)

print(f"\nEncontrados {stuck_profiles.count()} perfiles atascados\n")

for profile in stuck_profiles:
    print(f"Perfil ID: {profile.pk}")
    print(f"  Usuario: {profile.user.get_full_name()} ({profile.user.email})")
    print(f"  Estado actual: {profile.status}")
    print(f"  Última actualización: {profile.updated_at}")
    
    # Cambiar a 'rejected' con mensaje explicativo
    rejection_reason = {
        'code': 'VERIFICATION_TIMEOUT',
        'message': 'El proceso de verificación no se completó correctamente. '
                   'Por favor, verifica que todas tus imágenes sean claras y legibles, '
                   'y solicita una nueva verificación.'
    }
    
    profile.status = 'rejected'
    profile.rejection_reasons = json.dumps([rejection_reason])
    profile.rejected_at = timezone.now()
    profile.save()
    
    print(f"  ✅ Actualizado a: rejected")
    print(f"  📧 Recomendación: El usuario puede re-solicitar verificación\n")

print("=" * 60)
print("PROCESO COMPLETADO")
print("=" * 60)
print("\nLos usuarios pueden ahora:")
print("1. Ver que su verificación fue rechazada")
print("2. Revisar el motivo del rechazo")
print("3. Corregir sus imágenes")
print("4. Re-solicitar verificación (que ahora usará el código corregido)")
