# bookings/templatetags/custom_filters.py
from django import template
from django.utils import timezone
from datetime import timedelta

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
    """Convierte Decimal a string para usar en templates"""
    return str(value)