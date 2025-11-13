"""
SmartImageField - Campo de Imagen Inteligente para Django
==========================================================

Un ImageField personalizado que maneja URLs de forma inteligente según el entorno,
eliminando la necesidad de lógica condicional en templates, serializers y vistas.

Autor: Tu equipo de desarrollo
Fecha: 2025
Versión: 2.0
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

# Obtener configuración del entorno
environment = getattr(settings, 'ENVIRONMENT', 'local').lower()

class SmartImageFieldFile(models.fields.files.ImageFieldFile):
    """
    Wrapper personalizado para el archivo de imagen que sobrescribe
    el comportamiento de la propiedad 'url'.
    """
    
    def _is_url(self):
        """Verifica si name es una URL completa"""
        return self.name and (self.name.startswith('http://') or self.name.startswith('https://'))
    
    def _get_smart_url(self):
        """
        Retorna la URL apropiada basándose en el entorno.
        
        Returns:
            str: URL completa en local/desarrollo, path relativo en producción
        """
        if not self.name:
            return ''
        
        try:
            # Si el name ya es una URL completa, retornarla directamente
            if self._is_url():
                return self.name
            
            # Si el campo tiene force_full_url activado, siempre retornar URL completa
            if hasattr(self.field, 'force_full_url') and self.field.force_full_url:
                return self.storage.url(self.name)
            
            # Producción: retornar solo el path relativo
            if environment == 'production':
                return self.name
            
            # Local/Desarrollo/Staging: retornar URL completa
            return self.storage.url(self.name)
            
        except Exception as e:
            logger.error(f"Error al generar URL para {self.name}: {str(e)}")
            return self.storage.url(self.name)
    
    @property
    def url(self):
        """Sobrescribe la propiedad url para usar nuestra lógica inteligente"""
        return self._get_smart_url()
    
    @property
    def size(self):
        """Evita que Django intente acceder al archivo si es una URL"""
        if self._is_url():
            return 0  # O podrías hacer una petición HEAD para obtener el tamaño real
        return super().size
    
    def _require_file(self):
        """Sobrescribe para evitar validación de archivo cuando es URL"""
        if self._is_url():
            return
        super()._require_file()


class SmartImageField(models.ImageField):
    """
    ImageField que ajusta automáticamente el comportamiento de .url según el entorno.
    
    Características:
    ----------------
    - En LOCAL: Retorna URL completa (ej: /media/profiles/photo.jpg)
    - En PRODUCTION: Retorna solo el path (ej: profiles/photo.jpg)
    - Compatible con Django Admin
    - Compatible con Django REST Framework
    - Sin cambios en la base de datos
    - Zero breaking changes
    
    Parámetros adicionales:
    -----------------------
    force_full_url : bool, default=False
        Si True, siempre retorna URL completa independientemente del entorno.
        Útil para casos especiales como emails o webhooks.
    
    Uso básico:
    -----------
    class MyModel(models.Model):
        photo = SmartImageField(
            'Foto de Perfil',
            upload_to='profiles/',
            blank=True,
            max_length=255
        )
    
    En templates:
    -------------
    <img src="{{ object.photo.url }}" />  {# Funciona en todos los entornos #}
    
    En serializers (DRF):
    ---------------------
    class MySerializer(serializers.ModelSerializer):
        class Meta:
            model = MyModel
            fields = ['photo']  # Automáticamente funciona correctamente
    
    Caso especial (forzar URL completa):
    -----------------------------------
    class EmailModel(models.Model):
        attachment = SmartImageField(
            upload_to='emails/',
            force_full_url=True  # Siempre URL completa para emails
        )
    """
    
    # Especificar el FileField personalizado que usaremos
    attr_class = SmartImageFieldFile
    
    def __init__(self, verbose_name=None, name=None, force_full_url=False, **kwargs):
        """
        Inicializa el SmartImageField
        
        Args:
            verbose_name: Nombre legible del campo
            name: Nombre interno del campo
            force_full_url: Si True, siempre retorna URL completa
            **kwargs: Argumentos adicionales de ImageField
        """
        self.force_full_url = force_full_url
        super().__init__(verbose_name, name, **kwargs)
    
    def deconstruct(self):
        """
        Necesario para las migraciones de Django.
        Retorna los argumentos necesarios para reconstruir el campo.
        """
        name, path, args, kwargs = super().deconstruct()
        
        # Agregar force_full_url a kwargs si no es el default
        if self.force_full_url is not False:
            kwargs['force_full_url'] = self.force_full_url
        
        return name, path, args, kwargs
    
    def formfield(self, **kwargs):
        """
        Retorna el widget de formulario para Django Admin.
        Mantiene la compatibilidad completa con el admin.
        """
        return super().formfield(**kwargs)
    

class SmartFileField(models.FileField):
    """
    Similar a SmartImageField pero para archivos en general (PDFs, documentos, etc.)
    
    Uso:
    ----
    class Document(models.Model):
        contract = SmartFileField(
            'Contrato',
            upload_to='contracts/',
            blank=True
        )
        
        invoice = SmartFileField(
            'Factura',
            upload_to='invoices/',
            force_full_url=True  # Para enviar por email
        )
    """
    
    attr_class = SmartImageFieldFile  # Reutilizamos la misma lógica
    
    def __init__(self, verbose_name=None, name=None, force_full_url=False, **kwargs):
        self.force_full_url = force_full_url
        super().__init__(verbose_name, name, **kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.force_full_url is not False:
            kwargs['force_full_url'] = self.force_full_url
        return name, path, args, kwargs
