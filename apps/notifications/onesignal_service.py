import json
import os
import ssl
import urllib.request
from django.conf import settings

class OneSignalService:
    """
    Servicio simple para enviar notificaciones Push a través de OneSignal API v1
    """
    
    BASE_URL = "https://onesignal.com/api/v1/notifications"
    
    @classmethod
    def send_notification(cls, player_ids, title, message, url=None, data=None):
        """
        Envía una notificación a una lista de player_ids
        """
        if not player_ids:
            return False, "No player_ids provided"
            
        # Asegurarse que player_ids es una lista
        if isinstance(player_ids, str):
            player_ids = [player_ids]
            
        app_id = getattr(settings, 'ONESIGNAL_APP_ID', os.getenv('ONESIGNAL_APP_ID'))
        api_key = getattr(settings, 'ONESIGNAL_REST_API_KEY', os.getenv('ONESIGNAL_REST_API_KEY'))
        
        if not app_id or not api_key:
            return False, "OneSignal credentials missing in settings"

        header = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Basic {api_key}"
        }

        payload = {
            "app_id": app_id,
            "include_player_ids": player_ids,
            "headings": {"en": title, "es": title},
            "contents": {"en": message, "es": message},
        }

        if url:
            payload["url"] = url
            
        if data:
            payload["data"] = data

        try:
            req = urllib.request.Request(
                cls.BASE_URL, 
                data=json.dumps(payload).encode('utf-8'), 
                headers=header
            )
            
            # Contexto SSL seguro
            context = ssl.create_default_context()
            
            with urllib.request.urlopen(req, context=context) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
                if 'errors' in response_data:
                    return False, response_data['errors']
                
                return True, response_data
                
        except urllib.error.HTTPError as e:
            error_content = e.read().decode('utf-8')
            return False, f"HTTP Error {e.code}: {error_content}"
        except Exception as e:
            return False, str(e)

    @classmethod
    def send_to_user(cls, user, title, message, url=None):
        """Helper para enviar a un usuario Django específico"""
        if not hasattr(user, 'profile') or not user.profile.onesignal_player_id:
            return False, "User has no OneSignal Player ID"
            
        return cls.send_notification(
            player_ids=[user.profile.onesignal_player_id],
            title=title,
            message=message,
            url=url
        )
