# bookings/templatetags/custom_filters.py
from django import template
from django.utils import timezone
from decimal import Decimal

register = template.Library()

@register.filter
def timeuntil(value, arg=None):
    """
    Calcula el tiempo hasta una fecha.
    Si arg='hours', retorna horas, sino retorna días.
    """
    if not value:
        return 0
    
    now = timezone.now()
    if value < now:
        return 0
    
    delta = value - now
    
    if arg == 'hours':
        return int(delta.total_seconds() / 3600)
    else:
        return delta.days

@register.filter
def to_string(value):
    """
    Convierte un Decimal a string con formato internacional (punto, no coma)
    Útil para inputs type="number" en HTML
    """
    if value is None:
        return ""
    
    # Convertir a string y reemplazar coma con punto
    str_value = str(value).replace(',', '.')
    return str_value

@register.filter(name='getattribute')
def getattribute(obj, attr_name):
    """
    Obtiene dinámicamente un atributo de un objeto.
    Uso: {{ object|getattribute:"field_name" }}
    """
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return None