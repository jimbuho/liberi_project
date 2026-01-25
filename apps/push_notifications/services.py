import json
import logging
import requests
from django.conf import settings
from django.contrib.auth.models import User
from .models import PushSubscription, PushNotificationLog


logger = logging.getLogger(__name__)


class OneSignalService:
    """
    Servicio para enviar notificaciones push usando OneSignal
    """
    
    API_URL = "https://onesignal.com/api/v1/notifications"
    
    @staticmethod
    def send_notification(user: User = None, player_ids: list = None, 
                         title: str = "", message: str = "", 
                         notification_type: str = "general",
                         data: dict = None, url: str = None):
        """
        Envía una notificación push a un usuario o lista de player_ids
        
        Args:
            user: Usuario al que enviar (usa sus player_ids registrados)
            player_ids: Lista de player_ids específicos (alternativa a user)
            title: Título de la notificación
            message: Mensaje de la notificación
            notification_type: Tipo (booking_created, booking_accepted, etc.)
            data: Datos adicionales para el payload
            url: URL a abrir cuando se hace click en la notificación
            
        Returns:
            PushNotificationLog: Objeto con el registro del envío
        """
        
        # Validar configuración
        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            logger.info("Push notifications desactivadas en settings")
            return OneSignalService._create_log(
                user=user,
                player_ids=[],
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
                status='failed',
                error_message='Push notifications desactivadas'
            )
        
        if not settings.ONESIGNAL_APP_ID or not settings.ONESIGNAL_REST_API_KEY:
            logger.error("OneSignal no configurado correctamente")
            return OneSignalService._create_log(
                user=user,
                player_ids=[],
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
                status='failed',
                error_message='OneSignal no configurado'
            )
        
        # Obtener player_ids
        target_player_ids = player_ids or []
        
        if user and not target_player_ids:
            # Obtener player_ids del usuario
            subscriptions = PushSubscription.objects.filter(
                user=user,
                is_active=True
            )
            target_player_ids = list(subscriptions.values_list('player_id', flat=True))
        
        if not target_player_ids:
            logger.warning(f"No hay player_ids para enviar notificación a {user.username if user else 'usuario desconocido'}")
            return OneSignalService._create_log(
                user=user,
                player_ids=[],
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
                status='failed',
                error_message='No hay dispositivos suscritos'
            )
        
        # Preparar payload
        payload = {
            "app_id": settings.ONESIGNAL_APP_ID,
            "include_player_ids": target_player_ids,
            "headings": {"en": title},
            "contents": {"en": message},
        }
        
        # Agregar URL si se especifica
        if url:
            payload["url"] = url
        
        # Agregar datos adicionales
        if data:
            payload["data"] = data
        else:
            payload["data"] = {
                "type": notification_type
            }
        
        # Headers
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}"
        }
        
        logger.info(f"📱 Enviando Push notification '{notification_type}' a {len(target_player_ids)} dispositivo(s)")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            # Enviar a OneSignal
            response = requests.post(
                OneSignalService.API_URL,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            logger.info(f"✅ Push notification enviada exitosamente")
            logger.debug(f"Response: {json.dumps(response_data, indent=2)}")
            
            # Crear log exitoso
            return OneSignalService._create_log(
                user=user,
                player_ids=target_player_ids,
                notification_type=notification_type,
                title=title,
                message=message,
                data=payload.get("data"),
                status='sent',
                onesignal_id=response_data.get('id'),
                response=json.dumps(response_data)
            )
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error en request a OneSignal: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            # Intentar obtener detalles del error
            try:
                if hasattr(e, 'response') and e.response is not None:
                    error_details = e.response.json()
                    error_msg = f"{error_msg} - Details: {json.dumps(error_details)}"
            except:
                pass
            
            return OneSignalService._create_log(
                user=user,
                player_ids=target_player_ids,
                notification_type=notification_type,
                title=title,
                message=message,
                data=payload.get("data"),
                status='failed',
                error_message=error_msg
            )
            
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            
            return OneSignalService._create_log(
                user=user,
                player_ids=target_player_ids,
                notification_type=notification_type,
                title=title,
                message=message,
                data=payload.get("data"),
                status='failed',
                error_message=error_msg
            )
    
    @staticmethod
    def _create_log(user, player_ids, notification_type, title, message, 
                    data, status, onesignal_id=None, response=None, error_message=None):
        """Crea un registro del envío de notificación"""
        return PushNotificationLog.objects.create(
            user=user,
            player_ids=player_ids,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
            status=status,
            onesignal_id=onesignal_id,
            response=response,
            error_message=error_message
        )
    
    @staticmethod
    def register_device(user: User, player_id: str, device_type: str = "Web"):
        """
        Registra un dispositivo para recibir push notifications
        
        Args:
            user: Usuario propietario del dispositivo
            player_id: Player ID de OneSignal
            device_type: Tipo de dispositivo (Web, Android, iOS)
            
        Returns:
            PushSubscription: Objeto de suscripción creado o existente
        """
        subscription, created = PushSubscription.objects.update_or_create(
            player_id=player_id,
            defaults={
                'user': user,
                'device_type': device_type,
                'is_active': True
            }
        )
        
        action = "registrado" if created else "actualizado"
        logger.info(f"📱 Dispositivo {action}: {user.username} - {player_id[:20]}...")
        
        return subscription
    
    @staticmethod
    def unregister_device(player_id: str):
        """
        Desactiva un dispositivo
        """
        try:
            subscription = PushSubscription.objects.get(player_id=player_id)
            subscription.is_active = False
            subscription.save()
            logger.info(f"🔕 Dispositivo desactivado: {player_id[:20]}...")
            return True
        except PushSubscription.DoesNotExist:
            logger.warning(f"⚠️ Player ID no encontrado: {player_id}")
            return False
    
    @staticmethod
    def get_user_devices(user: User):
        """
        Obtiene todos los dispositivos activos de un usuario
        """
        return PushSubscription.objects.filter(
            user=user,
            is_active=True
        )
