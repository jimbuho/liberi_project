import logging
from apps.core.models import City

logger = logging.getLogger(__name__)

def get_current_city(request):
    """Obtiene la ciudad actual del usuario o de sesión"""
    # 1. De perfil si está autenticado
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.current_city:
            # logger.info(f"get_current_city - Desde perfil usuario: {request.user.profile.current_city.name}")
            return request.user.profile.current_city
    
    # 2. De sesión
    city_id = request.session.get('current_city_id')
    if city_id:
        try:
            city = City.objects.get(id=city_id, active=True)
            # logger.info(f"get_current_city - Desde sesión: {city.name} (ID: {city_id})")
            return city
        except City.DoesNotExist:
            # logger.warning(f"get_current_city - Ciudad ID {city_id} no existe en DB")
            pass
    
    # 3. Default: primera ciudad activa
    default_city = City.objects.filter(active=True).order_by('display_order').first()
    if default_city:
        pass
        # logger.info(f"get_current_city - Default (primera ciudad): {default_city.name}")
    else:
        logger.error("get_current_city - ⚠️ NO HAY CIUDADES ACTIVAS EN EL SISTEMA")
    return default_city
