import logging
import re
from django.conf import settings
from django.utils import timezone
from .models import ProviderProfile, Service

logger = logging.getLogger(__name__)

MODO_DEBUG = True

def validate_provider_profile(provider_profile):
    """
    Algoritmo principal de validación de proveedor.
    Retorna: (is_approved: bool, rejection_reasons: list, warnings: list)
    """
    rejection_reasons = []
    warnings = []
    security_alerts = []
    
    logger.info(f"🔍 [AGENTE VERIFICACIÓN] Iniciando análisis para proveedor: {provider_profile.user.username} (ID: {provider_profile.pk})")
    if MODO_DEBUG: print(f"🔍 [AGENTE VERIFICACIÓN] Iniciando análisis para proveedor: {provider_profile.user.username} (ID: {provider_profile.pk})")
    
    # Obtener primer servicio
    logger.info("🔍 [AGENTE VERIFICACIÓN] Buscando primer servicio creado...")
    if MODO_DEBUG: print("🔍 [AGENTE VERIFICACIÓN] Buscando primer servicio creado...")
    first_service = Service.objects.filter(
        provider=provider_profile.user,
        available=True
    ).order_by('created_at').first()
    
    if not first_service:
        logger.warning("❌ [AGENTE VERIFICACIÓN] FALLO: No se encontró ningún servicio activo.")
        if MODO_DEBUG: print("❌ [AGENTE VERIFICACIÓN] FALLO: No se encontró ningún servicio activo.")
        rejection_reasons.append({
            'code': 'NO_SERVICE',
            'message': 'Debes crear al menos un servicio antes de solicitar verificación.'
        })
        return False, rejection_reasons, warnings
    
    logger.info(f"✅ [AGENTE VERIFICACIÓN] Servicio encontrado: {first_service.name}")
    if MODO_DEBUG: print(f"✅ [AGENTE VERIFICACIÓN] Servicio encontrado: {first_service.name}")

    # FASE 1: Validaciones de Completitud
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 1: Validando completitud del perfil...")
    if MODO_DEBUG: print("🔍 [AGENTE VERIFICACIÓN] FASE 1: Validando completitud del perfil...")
    completeness_result = validate_profile_completeness(provider_profile)
    if completeness_result['rejections']:
        logger.warning(f"❌ [AGENTE VERIFICACIÓN] FASE 1 FALLÓ: {len(completeness_result['rejections'])} errores encontrados.")
        if MODO_DEBUG: print(f"❌ [AGENTE VERIFICACIÓN] FASE 1 FALLÓ: {len(completeness_result['rejections'])} errores encontrados.")
        for rej in completeness_result['rejections']:
            logger.warning(f"   - {rej['code']}: {rej['message']}")
    else:
        logger.info("✅ [AGENTE VERIFICACIÓN] FASE 1 APROBADA: Perfil completo.")
        if MODO_DEBUG: print("✅ [AGENTE VERIFICACIÓN] FASE 1 APROBADA: Perfil completo.")
        
    rejection_reasons.extend(completeness_result['rejections'])
    
    # Si falla completitud básica, retornar temprano
    if rejection_reasons:
        logger.info("🛑 [AGENTE VERIFICACIÓN] Deteniendo validación por fallos en FASE 1.")
        if MODO_DEBUG: print("🛑 [AGENTE VERIFICACIÓN] Deteniendo validación por fallos en FASE 1.")
        return False, rejection_reasons, warnings

    # FASE 2: Validaciones de Documentos (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 2: Analizando documentos de identidad (IA Vision)...")
    print("🔍 [AGENTE VERIFICACIÓN] FASE 2: Analizando documentos de identidad (IA Vision)...")
    documents_result = validate_identity_documents(provider_profile)
    if documents_result['rejections']:
        logger.warning(f"❌ [AGENTE VERIFICACIÓN] FASE 2 FALLÓ: {len(documents_result['rejections'])} problemas con documentos.")
        if MODO_DEBUG: print(f"❌ [AGENTE VERIFICACIÓN] FASE 2 FALLÓ: {len(documents_result['rejections'])} problemas con documentos.")
        for rej in documents_result['rejections']:
            logger.warning(f"   - {rej['code']}: {rej['message']}")
            print(f"   - {rej['code']}: {rej['message']}")
    else:
        logger.info("✅ [AGENTE VERIFICACIÓN] FASE 2 APROBADA: Documentos válidos.")    
        if MODO_DEBUG: print("✅ [AGENTE VERIFICACIÓN] FASE 2 APROBADA: Documentos válidos.")
        
    rejection_reasons.extend(documents_result['rejections'])
    
    # FASE 3: Validaciones de Coherencia (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 3: Analizando coherencia semántica (IA NLP)...")
    if MODO_DEBUG: print("🔍 [AGENTE VERIFICACIÓN] FASE 3: Analizando coherencia semántica (IA NLP)...")
    coherence_result = validate_coherence(provider_profile, first_service)
    rejection_reasons.extend(coherence_result['rejections'])
    warnings.extend(coherence_result['warnings'])
    if not coherence_result['rejections']:
         logger.info("✅ [AGENTE VERIFICACIÓN] FASE 3 APROBADA: Coherencia validada.")
         if MODO_DEBUG: print("✅ [AGENTE VERIFICACIÓN] FASE 3 APROBADA: Coherencia validada.")
    
    # FASE 4: Validaciones de Contenido Prohibido (Imágenes) (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 4: Moderación de contenido visual (IA Safety)...")
    if MODO_DEBUG: print("🔍 [AGENTE VERIFICACIÓN] FASE 4: Moderación de contenido visual (IA Safety)...")
    image_content_result = validate_image_content(provider_profile, first_service)
    rejection_reasons.extend(image_content_result['rejections'])
    security_alerts.extend(image_content_result['alerts'])
    if not image_content_result['rejections']:
         logger.info("✅ [AGENTE VERIFICACIÓN] FASE 4 APROBADA: Imágenes seguras.")
         print("✅ [AGENTE VERIFICACIÓN] FASE 4 APROBADA: Imágenes seguras.")
    
    # FASE 5: Validaciones de Contenido Prohibido (Texto) (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 5: Moderación de texto (IA Safety)...")
    print("🔍 [AGENTE VERIFICACIÓN] FASE 5: Moderación de texto (IA Safety)...")
    text_content_result = validate_text_content(provider_profile, first_service)
    rejection_reasons.extend(text_content_result['rejections'])
    security_alerts.extend(text_content_result['alerts'])
    if not text_content_result['rejections']:
         logger.info("✅ [AGENTE VERIFICACIÓN] FASE 5 APROBADA: Texto seguro.") 
         if MODO_DEBUG: print("✅ [AGENTE VERIFICACIÓN] FASE 5 APROBADA: Texto seguro.")
    
    # Procesar alertas de seguridad (TODO)
    # if security_alerts:
    #     flag_for_manual_review(provider_profile, security_alerts)
    
    # Determinar resultado
    is_approved = len(rejection_reasons) == 0
    
    if is_approved:
        logger.info("🎉 [AGENTE VERIFICACIÓN] RESULTADO FINAL: APROBADO. El perfil cumple con todos los requisitos.")
        if MODO_DEBUG: print("🎉 [AGENTE VERIFICACIÓN] RESULTADO FINAL: APROBADO. El perfil cumple con todos los requisitos.")
    else:
        logger.info(f"🚫 [AGENTE VERIFICACIÓN] RESULTADO FINAL: RECHAZADO. Se encontraron {len(rejection_reasons)} motivos de rechazo.")
        if MODO_DEBUG: print(f"🚫 [AGENTE VERIFICACIÓN] RESULTADO FINAL: RECHAZADO. Se encontraron {len(rejection_reasons)} motivos de rechazo.")
    
    return is_approved, rejection_reasons, warnings

def validate_profile_completeness(provider_profile):
    """
    Valida que el perfil tenga la información básica requerida.
    """
    rejections = []
    config = settings.PROVIDER_VERIFICATION_CONFIG
    
    # CRITERIO 1: Fotografía de Perfil Presente
    logger.info("   - Verificando foto de perfil...")
    print("   - Verificando foto de perfil...")
    if not provider_profile.profile_photo:
        logger.warning("   ❌ Falta foto de perfil")
        if MODO_DEBUG: print("   ❌ Falta foto de perfil")
        rejections.append({
            'code': 'PROFILE_PHOTO_REQUIRED',
            'message': 'Tu perfil no tiene una fotografía de perfil. Por favor, sube una foto profesional.'
        })
    else:
        logger.info("   ✅ Foto de perfil presente")
        if MODO_DEBUG: print("   ✅ Foto de perfil presente")
    
    # CRITERIO 2: Descripción del Perfil Adecuada
    logger.info("   - Analizando descripción del perfil...")
    if MODO_DEBUG: print("   - Analizando descripción del perfil...")
    description = provider_profile.description or ""
    if len(description) < config['min_description_length']:
        logger.warning(f"   ❌ Descripción muy corta ({len(description)} chars)")
        if MODO_DEBUG: print(f"   ❌ Descripción muy corta ({len(description)} chars)")
        rejections.append({
            'code': 'PROFILE_DESCRIPTION_TOO_SHORT',
            'message': f'La descripción de tu perfil es muy corta. Mínimo {config["min_description_length"]} caracteres.'
        })
    elif len(description) > config['max_description_length']:
        logger.warning(f"   ❌ Descripción muy larga ({len(description)} chars)")
        if MODO_DEBUG: print(f"   ❌ Descripción muy larga ({len(description)} chars)")
        rejections.append({
            'code': 'PROFILE_DESCRIPTION_TOO_LONG',
            'message': f'La descripción de tu perfil es muy larga. Máximo {config["max_description_length"]} caracteres.'
        })
    else:
        logger.info(f"   ✅ Longitud de descripción correcta ({len(description)} chars)")
        if MODO_DEBUG: print(f"   ✅ Longitud de descripción correcta ({len(description)} chars)")
        
    # TODO: NLP check for professional content
    
    # CRITERIO 3: Coherencia Descripción-Categoría (Placeholder)
    # Se implementará con NLP en fases posteriores
    
    return {'rejections': rejections}

def validate_identity_documents(provider_profile):
    """
    MOCK: Valida documentos de identidad (OCR, reconocimiento facial).
    """
    rejections = []
    # TODO: Integrar AWS Rekognition / Textract
    
    # Simulación: Si no hay fotos de cédula, rechazar
    logger.info("   - Verificando documentos de identidad (Frontal/Dorso)...")
    if not provider_profile.id_card_front or not provider_profile.id_card_back:
        logger.warning("   ❌ Faltan imágenes de la cédula")
        if MODO_DEBUG: print("   ❌ Faltan imágenes de la cédula")
        rejections.append({
            'code': 'ID_DOCUMENTS_MISSING',
            'message': 'Faltan fotografías de tu cédula de identidad.'
        })
    else:
        logger.info("   ✅ Imágenes de cédula presentes")
        if MODO_DEBUG: print("   ✅ Imágenes de cédula presentes")
        
    logger.info("   - Verificando selfie de seguridad...")
    if not provider_profile.selfie_with_id:
        logger.warning("   ❌ Falta selfie con cédula")
        if MODO_DEBUG: print("   ❌ Falta selfie con cédula")
        rejections.append({
            'code': 'SELFIE_MISSING',
            'message': 'Falta la selfie sosteniendo tu cédula.'
        })
    else:
        logger.info("   ✅ Selfie presente")
        if MODO_DEBUG: print("   ✅ Selfie presente")
        
    return {'rejections': rejections}

def validate_coherence(provider_profile, service):
    """
    MOCK: Valida coherencia entre perfil y servicio.
    """
    rejections = []
    warnings = []
    # TODO: Integrar NLP para análisis semántico
    logger.info("   - [MOCK] Analizando coherencia entre categoría y descripción...")
    if MODO_DEBUG: print("   - [MOCK] Analizando coherencia entre categoría y descripción...")
    logger.info("   ✅ Coherencia validada (Simulado)")
    if MODO_DEBUG: print("   ✅ Coherencia validada (Simulado)")
    
    return {'rejections': rejections, 'warnings': warnings}

def validate_image_content(provider_profile, service):
    """
    MOCK: Valida contenido prohibido en imágenes.
    """
    rejections = []
    alerts = []
    # TODO: Integrar AWS Rekognition Moderation
    logger.info("   - [MOCK] Escaneando imágenes por contenido inapropiado...")
    if MODO_DEBUG: print("   - [MOCK] Escaneando imágenes por contenido inapropiado...")
    logger.info("   ✅ Imágenes limpias (Simulado)")
    if MODO_DEBUG: print("   ✅ Imágenes limpias (Simulado)")
    
    return {'rejections': rejections, 'alerts': alerts}

def validate_text_content(provider_profile, service):
    """
    MOCK: Valida contenido prohibido en texto.
    """
    rejections = []
    alerts = []
    # TODO: Integrar NLP para detección de contenido ilegal/contacto
    logger.info("   - [MOCK] Escaneando texto por PII o contenido prohibido...")
    if MODO_DEBUG: print("   - [MOCK] Escaneando texto por PII o contenido prohibido...")
    logger.info("   ✅ Texto limpio (Simulado)")
    if MODO_DEBUG: print("   ✅ Texto limpio (Simulado)")
    
    return {'rejections': rejections, 'alerts': alerts}

def trigger_validation_if_eligible(provider_profile):
    """
    Verifica si el perfil cumple condiciones para validación (Docs + Servicio)
    y dispara la tarea de validación respetando el entorno (Background/Inline).
    """
    from apps.core.models import Service
    from apps.core.tasks import validate_provider_profile_task
    from apps.core.email_utils import run_task
    
    # 1. Verificar documentos (Step 2 completado)
    has_documents = provider_profile.registration_step >= 2
    
    # 2. Verificar primer servicio
    has_service = Service.objects.filter(
        provider=provider_profile.user, 
        available=True
    ).exists()
    
    # 3. Verificar estado elegible
    is_eligible_status = provider_profile.status in ['created', 'resubmitted', 'pending']
    
    if has_documents and has_service and is_eligible_status:
        # Marcar como pendiente si no lo está
        if provider_profile.status != 'pending':
            provider_profile.status = 'pending'
            provider_profile.save()
            
        # Ejecutar tarea (run_task maneja dev=inline, prod=background)
        logger.info(f"🚀 Disparando validación para {provider_profile.user.username}")
        
        # FORZAR ejecución en línea para desarrollo (Solicitud explícita)
        if getattr(settings, 'ENVIRONMENT', 'development') == 'development':
            logger.info("🔧 [DEVELOPMENT] Ejecutando validación INMEDIATA (Síncrona)")
            validate_provider_profile_task(provider_profile.pk)
        else:
            run_task(validate_provider_profile_task, provider_profile.pk)
            
        return True
        
    return False
