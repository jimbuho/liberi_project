"""
Validadores para SmartImageField
=================================
Funciones validadoras que pueden ser serializadas por Django migrations.
NO usar lambdas - Django no puede serializarlas.
"""

from django.core.exceptions import ValidationError

import re

def validate_image_size_5mb(image):
    """Valida que la imagen no exceda 5MB"""
    max_size_mb = 5
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if image.size > max_size_bytes:
        raise ValidationError(
            f'El tamaño de la imagen no puede exceder {max_size_mb}MB. '
            f'Tamaño actual: {image.size / 1024 / 1024:.2f}MB'
        )


def validate_image_size_2mb(image):
    """Valida que la imagen no exceda 2MB"""
    max_size_mb = 2
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if image.size > max_size_bytes:
        raise ValidationError(
            f'El tamaño de la imagen no puede exceder {max_size_mb}MB. '
            f'Tamaño actual: {image.size / 1024 / 1024:.2f}MB'
        )


def validate_image_size_1mb(image):
    """Valida que la imagen no exceda 1MB"""
    max_size_mb = 1
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if image.size > max_size_bytes:
        raise ValidationError(
            f'El tamaño de la imagen no puede exceder {max_size_mb}MB. '
            f'Tamaño actual: {image.size / 1024 / 1024:.2f}MB'
        )


def validate_image_dimensions_800x800(image):
    """Valida que la imagen no exceda 800x800 pixels"""
    from PIL import Image as PILImage
    
    try:
        img = PILImage.open(image)
        width, height = img.size
        max_width = max_height = 800
        
        if width > max_width or height > max_height:
            raise ValidationError(
                f'Las dimensiones de la imagen no pueden exceder {max_width}x{max_height}px. '
                f'Dimensiones actuales: {width}x{height}px'
            )
    except Exception as e:
        raise ValidationError(f'Error al validar dimensiones: {str(e)}')


def validate_image_dimensions_1920x1080(image):
    """Valida que la imagen no exceda 1920x1080 pixels"""
    from PIL import Image as PILImage
    
    try:
        img = PILImage.open(image)
        width, height = img.size
        max_width, max_height = 1920, 1080
        
        if width > max_width or height > max_height:
            raise ValidationError(
                f'Las dimensiones de la imagen no pueden exceder {max_width}x{max_height}px. '
                f'Dimensiones actuales: {width}x{height}px'
            )
    except Exception as e:
        raise ValidationError(f'Error al validar dimensiones: {str(e)}')


def validate_image_dimensions_4096x4096(image):
    """Valida que la imagen no exceda 4096x4096 pixels"""
    from PIL import Image as PILImage
    
    try:
        img = PILImage.open(image)
        width, height = img.size
        max_width = max_height = 4096
        
        if width > max_width or height > max_height:
            raise ValidationError(
                f'Las dimensiones de la imagen no pueden exceder {max_width}x{max_height}px. '
                f'Dimensiones actuales: {width}x{height}px'
            )
    except Exception as e:
        raise ValidationError(f'Error al validar dimensiones: {str(e)}')


# ==============================================================
# FACTORY FUNCTION (OPCIONAL) - Para validadores personalizados
# ==============================================================

def create_image_size_validator(max_size_mb):
    """
    Crea un validador de tamaño de imagen dinámicamente.
    
    NOTA: Esta función no se puede usar directamente en models.py
    porque Django no puede serializar closures.
    
    Úsala solo si defines el validador en el mismo archivo models.py
    FUERA de la clase del modelo.
    
    Ejemplo:
        # En models.py, FUERA de la clase:
        validate_banner_size = create_image_size_validator(3)
        
        class MyModel(models.Model):
            banner = SmartImageField(
                upload_to='banners/',
                validators=[validate_banner_size]
            )
    """
    def validator(image):
        max_size_bytes = max_size_mb * 1024 * 1024
        if image.size > max_size_bytes:
            raise ValidationError(
                f'El tamaño de la imagen no puede exceder {max_size_mb}MB. '
                f'Tamaño actual: {image.size / 1024 / 1024:.2f}MB'
            )
    
    validator.__name__ = f'validate_image_size_{max_size_mb}mb'
    return validator


def create_image_dimensions_validator(max_width, max_height):
    """
    Crea un validador de dimensiones dinámicamente.
    
    NOTA: Igual que arriba, úsalo solo si defines el validador
    FUERA de la clase del modelo en models.py.
    """
    def validator(image):
        from PIL import Image as PILImage
        
        try:
            img = PILImage.open(image)
            width, height = img.size
            
            if width > max_width or height > max_height:
                raise ValidationError(
                    f'Las dimensiones no pueden exceder {max_width}x{max_height}px. '
                    f'Dimensiones actuales: {width}x{height}px'
                )
        except Exception as e:
            raise ValidationError(f'Error al validar dimensiones: {str(e)}')
    
    validator.__name__ = f'validate_dimensions_{max_width}x{max_height}'
    return validator

def validate_ecuador_phone(value):
    """
    Valida que el número de teléfono celular sea válido en Ecuador
    Formato: 09XXXXXXXX (10 dígitos)
    """
    if not value:
        return
    
    # Remover espacios y guiones
    cleaned = re.sub(r'[\s\-()]', '', value)
    
    # Validar celular (09 + 8 dígitos)
    if not re.match(r'^09\d{8}$', cleaned):
        raise ValidationError(
            'Ingrese un número celular válido de Ecuador. '
            'Formato: 09XXXXXXXX (10 dígitos)'
        )