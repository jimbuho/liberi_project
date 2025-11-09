from django import template
from decimal import Decimal

register = template.Library()

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
