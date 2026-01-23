from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@login_required
def save_player_id(request):
    """
    Guarda el OneSignal Player ID del usuario logueado.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            player_id = data.get('player_id')
            
            if not player_id:
                return JsonResponse({'success': False, 'error': 'No player_id provided'}, status=400)
            
            # Guardar en el perfil
            request.user.profile.onesignal_player_id = player_id
            request.user.profile.save()
            
            logger.info(f"Updated OneSignal Player ID for user {request.user.username}: {player_id}")
            
            return JsonResponse({'success': True})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error saving player_id: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
            
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
