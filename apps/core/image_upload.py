"""
core/image_upload.py

Sistema centralizado de carga de imágenes para Liberi MVP.
Detecta automáticamente el ambiente y usa:
- Supabase Storage en producción
- Sistema de archivos local en desarrollo

CORRECCIÓN APLICADA: En desarrollo, devuelve paths relativos sin /media/
para evitar duplicación cuando Django ImageField agrega MEDIA_URL automáticamente.

Uso:
    from core.image_upload import upload_image, delete_image
    
    # Subir imagen
    image_url = upload_image(
        file=request.FILES['photo'],
        folder='profiles',
        user_id=request.user.id
    )
    
    # Eliminar imagen
    delete_image(old_url)
"""

import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Detectar ambiente
IS_PRODUCTION = os.getenv('ENVIRONMENT', '').lower() == 'production'

# Importar Supabase solo en producción
if IS_PRODUCTION:
    try:
        from supabase import create_client
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "media")
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("⚠️ SUPABASE_URL o SUPABASE_KEY no configurados en producción")
            supabase = None
        else:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info(f"✅ Supabase configurado correctamente (Bucket: {SUPABASE_BUCKET})")
    except ImportError:
        logger.error("⚠️ supabase-py no instalado. Instalá con: pip install supabase")
        supabase = None
else:
    supabase = None
    logger.info("🔧 Modo desarrollo: usando almacenamiento local de Django")


def get_unique_filename(original_filename: str, prefix: Optional[str] = None) -> str:
    """
    Genera un nombre de archivo único manteniendo la extensión original
    
    Args:
        original_filename: Nombre original del archivo
        prefix: Prefijo opcional (ej: user_id)
    
    Returns:
        Nombre de archivo único
    """
    ext = original_filename.split('.')[-1].lower()
    unique_id = str(uuid.uuid4())[:8]
    
    if prefix:
        return f"{prefix}_{unique_id}.{ext}"
    return f"{unique_id}.{ext}"


def validate_image(file, max_size_mb: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Valida un archivo de imagen
    
    Args:
        file: Archivo a validar
        max_size_mb: Tamaño máximo en MB
    
    Returns:
        (es_valido, mensaje_error)
    """
    # Validar que existe
    if not file:
        return False, "No se proporcionó ningún archivo"
    
    # Validar extensión
    allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    ext = file.name.split('.')[-1].lower()
    
    if ext not in allowed_extensions:
        return False, f"Formato no permitido. Use: {', '.join(allowed_extensions)}"
    
    # Validar tamaño
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        return False, f"El archivo es demasiado grande. Máximo: {max_size_mb}MB"
    
    return True, None


def upload_image(
    file,
    folder: str = 'general',
    user_id: Optional[int] = None,
    unique_name: bool = True,
    validate: bool = True,
    max_size_mb: int = 5,
    prefix='user'
) -> str:
    """
    Sube una imagen al storage apropiado según el ambiente
    
    Args:
        file: Archivo de Django (request.FILES['field'])
        folder: Carpeta de destino (profiles, services, documents, etc.)
        user_id: ID del usuario (opcional, se usará como prefijo)
        unique_name: Si True, genera nombre único para evitar colisiones
        validate: Si True, valida el archivo antes de subir
        max_size_mb: Tamaño máximo permitido en MB
    
    Returns:
        En producción: URL pública completa de Supabase
        En desarrollo: Path relativo (Django agregará MEDIA_URL automáticamente)
    
    Raises:
        ValueError: Si la validación falla
        Exception: Si ocurre un error durante la carga
    """
    # Validar archivo
    if validate:
        is_valid, error_msg = validate_image(file, max_size_mb)
        if not is_valid:
            raise ValueError(error_msg)
    
    # Generar nombre de archivo
    if unique_name:
        name_with_prefix = f"{prefix}_{user_id}" if user_id else None
        filename = get_unique_filename(file.name, name_with_prefix)
    else:
        filename = file.name
    
    # Construir path completo
    file_path = f"{folder}/{filename}"
    
    try:
        if IS_PRODUCTION and supabase:
            # ========================================
            # PRODUCCIÓN: Subir a Supabase Storage
            # ========================================
            logger.info(f"📤 Subiendo a Supabase: {file_path}")
            
            # Leer contenido del archivo
            file_content = file.read()
            
            # Subir a Supabase (upsert=true para sobrescribir si existe)
            response = supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": file.content_type, "upsert": "true"}
            )
            
            # Obtener URL pública
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)
            
            logger.info(f"✅ Imagen subida exitosamente a Supabase: {file_path}")
            return public_url
            
        else:
            # ========================================
            # DESARROLLO: Guardar en almacenamiento local
            # ========================================
            logger.info(f"💾 Guardando localmente: {file_path}")
            
            # Guardar archivo usando el storage de Django
            saved_path = default_storage.save(file_path, ContentFile(file.read()))
            
            # CORRECCIÓN: En desarrollo, devolver solo el path relativo
            # Django ImageField agregará automáticamente MEDIA_URL al hacer .url
            # Esto evita la duplicación /media/media/
            public_url = saved_path
            
            print(f"✅ Imagen guardada localmente: {public_url}")
            logger.info(f"✅ Imagen guardada localmente (path relativo): {saved_path}")
            return public_url
            
    except Exception as e:
        logger.error(f"❌ Error al subir imagen: {str(e)}")
        raise Exception(f"Error al subir la imagen: {str(e)}")


def delete_image(image_url) -> bool:
    """
    Elimina una imagen del storage
    
    Args:
        image_url: URL de la imagen a eliminar (puede ser string o ImageFieldFile)
    
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    if not image_url:
        return False
    
    # CORRECCIÓN: Convertir ImageFieldFile a string
    # Django ImageField devuelve ImageFieldFile, no string
    if hasattr(image_url, 'name'):
        # Es un ImageFieldFile, extraer el path completo
        image_url = str(image_url)
    elif not isinstance(image_url, str):
        # Si no es string ni ImageFieldFile, convertir
        image_url = str(image_url)
    
    try:
        if IS_PRODUCTION and supabase:
            # ========================================
            # PRODUCCIÓN: Eliminar de Supabase
            # ========================================
            # Extraer el path del archivo de la URL
            # Ej: https://xyz.supabase.co/storage/v1/object/public/media/profiles/image.jpg
            # -> profiles/image.jpg
            
            parts = image_url.split(f"{SUPABASE_BUCKET}/")
            if len(parts) < 2:
                logger.warning(f"⚠️ No se pudo extraer el path de: {image_url}")
                return False
            
            file_path = parts[1]
            
            logger.info(f"🗑️ Eliminando de Supabase: {file_path}")
            supabase.storage.from_(SUPABASE_BUCKET).remove([file_path])
            logger.info(f"✅ Imagen eliminada de Supabase")
            return True
            
        else:
            # ========================================
            # DESARROLLO: Eliminar del almacenamiento local
            # ========================================
            # El path puede venir con o sin MEDIA_URL, normalizarlo
            relative_path = image_url
            
            # Remover /media/ si está presente
            if image_url.startswith('/media/'):
                relative_path = image_url.replace('/media/', '', 1)
            elif hasattr(settings, 'MEDIA_URL') and image_url.startswith(settings.MEDIA_URL):
                relative_path = image_url.replace(settings.MEDIA_URL, '', 1)
            
            logger.info(f"🗑️ Eliminando localmente: {relative_path}")
            
            if default_storage.exists(relative_path):
                default_storage.delete(relative_path)
                logger.info(f"✅ Imagen eliminada localmente")
                return True
            else:
                logger.warning(f"⚠️ Archivo no encontrado: {relative_path}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error al eliminar imagen: {str(e)}")
        return False


def replace_image(old_url, new_file, **kwargs) -> str:
    """
    Reemplaza una imagen: elimina la antigua y sube la nueva
    
    Args:
        old_url: URL de la imagen a reemplazar (puede ser string o ImageFieldFile)
        new_file: Nuevo archivo a subir
        **kwargs: Argumentos adicionales para upload_image()
    
    Returns:
        URL de la nueva imagen (completa en producción, relativa en desarrollo)
    """
    try:
        # Subir nueva imagen primero
        new_url = upload_image(new_file, **kwargs)
        
        # Si la nueva imagen se subió correctamente, eliminar la antigua
        if old_url:
            delete_image(old_url)
        
        return new_url
        
    except Exception as e:
        logger.error(f"❌ Error al reemplazar imagen: {str(e)}")
        raise


def get_image_info(image_url) -> dict:
    """
    Obtiene información sobre una imagen
    
    Args:
        image_url: URL de la imagen (puede ser string o ImageFieldFile)
    
    Returns:
        Diccionario con información de la imagen
    """
    # Convertir ImageFieldFile a string si es necesario
    if hasattr(image_url, 'name'):
        image_url = str(image_url)
    elif image_url and not isinstance(image_url, str):
        image_url = str(image_url)
    
    return {
        'url': image_url,
        'storage_type': 'supabase' if IS_PRODUCTION else 'local',
        'exists': bool(image_url),
        'environment': 'production' if IS_PRODUCTION else 'development'
    }


# ========================================
# HELPERS ESPECÍFICOS POR TIPO DE IMAGEN
# ========================================

def upload_profile_photo(file, user_id: int) -> str:
    """Sube una foto de perfil de proveedor"""
    return upload_image(
        file=file,
        folder='profiles',
        user_id=user_id,
        unique_name=True,
        max_size_mb=5,
        prefix='profile'
    )


def upload_service_image(file, provider_id: int) -> str:
    """Sube una imagen de servicio"""
    return upload_image(
        file=file,
        folder='services',
        user_id=provider_id,
        unique_name=True,
        max_size_mb=5,
        prefix='service'
    )


def upload_document(file, user_id: int, doc_type: str = 'general') -> str:
    """Sube un documento (cédula, contratos, etc.)"""
    return upload_image(
        file=file,
        folder=f'documents/{doc_type}',
        user_id=user_id,
        unique_name=True,
        max_size_mb=10,
        validate=False,
        prefix='doc'
    )


def upload_payment_proof(file, booking_id: str) -> str:
    """Sube un comprobante de pago"""
    return upload_image(
        file=file,
        folder='payment_proofs',
        user_id=None,
        unique_name=True,
        max_size_mb=5,
        prefix='transfer'
    )


# ========================================
# INFORMACIÓN DEL SISTEMA
# ========================================

def get_storage_info() -> dict:
    """
    Retorna información sobre el sistema de almacenamiento actual
    """
    info = {
        'environment': 'production' if IS_PRODUCTION else 'development',
        'storage_backend': 'Supabase Storage' if IS_PRODUCTION else 'Django Local Storage',
        'supabase_configured': bool(supabase) if IS_PRODUCTION else None,
    }
    
    if IS_PRODUCTION:
        info.update({
            'supabase_url': SUPABASE_URL if SUPABASE_URL else 'Not configured',
            'supabase_bucket': SUPABASE_BUCKET if supabase else 'Not configured',
        })
    else:
        info.update({
            'media_root': settings.MEDIA_ROOT if hasattr(settings, 'MEDIA_ROOT') else 'Not configured',
            'media_url': settings.MEDIA_URL if hasattr(settings, 'MEDIA_URL') else 'Not configured',
        })
    
    return info


# ========================================
# EJEMPLO DE USO
# ========================================

"""
EJEMPLO 1: En una vista simple
------------------------------
from core.image_upload import upload_profile_photo, delete_image

@login_required
def update_profile(request):
    if request.method == 'POST' and request.FILES.get('photo'):
        try:
            # Subir nueva foto
            new_photo_url = upload_profile_photo(
                file=request.FILES['photo'],
                user_id=request.user.id
            )
            
            # Eliminar foto anterior si existe
            if request.user.provider_profile.profile_photo:
                delete_image(request.user.provider_profile.profile_photo)
            
            # Guardar nueva URL/path
            request.user.provider_profile.profile_photo = new_photo_url
            request.user.provider_profile.save()
            
            messages.success(request, 'Foto actualizada exitosamente')
        except Exception as e:
            messages.error(request, f'Error al subir foto: {str(e)}')
    
    return render(request, 'profile_edit.html')


EJEMPLO 2: Con reemplazo automático
-----------------------------------
from core.image_upload import replace_image

@login_required
def update_service_image(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    
    if request.FILES.get('image'):
        try:
            # Reemplazar imagen (elimina antigua y sube nueva)
            new_url = replace_image(
                old_url=service.image,
                new_file=request.FILES['image'],
                folder='services',
                user_id=request.user.id
            )
            
            service.image = new_url
            service.save()
            
            messages.success(request, 'Imagen actualizada')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect('service_detail', service_id=service.id)


EJEMPLO 3: Validación manual
-----------------------------
from core.image_upload import validate_image, upload_image

def custom_upload(request):
    file = request.FILES.get('image')
    
    # Validar primero
    is_valid, error = validate_image(file, max_size_mb=3)
    if not is_valid:
        return JsonResponse({'error': error}, status=400)
    
    # Subir
    try:
        url = upload_image(file, folder='custom', validate=False)
        return JsonResponse({'url': url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
"""