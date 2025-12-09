import logging
import re
import json
from django.conf import settings
from django.utils import timezone
from .models import ProviderProfile, Service
from .verification_helpers import VerificationHelpers

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
    
    # Obtener primer servicio
    logger.info("🔍 [AGENTE VERIFICACIÓN] Buscando primer servicio creado...")
    first_service = Service.objects.filter(
        provider=provider_profile.user,
        available=True
    ).order_by('created_at').first()
    
    if not first_service:
        logger.warning("❌ [AGENTE VERIFICACIÓN] FALLO: No se encontró ningún servicio activo.")
        rejection_reasons.append({
            'code': 'NO_SERVICE',
            'message': 'Debes crear al menos un servicio antes de solicitar verificación.'
        })
        return False, rejection_reasons, warnings
    
    logger.info(f"✅ [AGENTE VERIFICACIÓN] Servicio encontrado: {first_service.name}")

    # FASE 1: Validaciones de Completitud
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 1: Validando completitud del perfil...")
    completeness_result = validate_profile_completeness(provider_profile)
    if completeness_result['rejections']:
        logger.warning(f"❌ [AGENTE VERIFICACIÓN] FASE 1 FALLÓ: {len(completeness_result['rejections'])} errores encontrados.")
        for rej in completeness_result['rejections']:
            logger.warning(f"   - {rej['code']}: {rej['message']}")
    else:
        logger.info("✅ [AGENTE VERIFICACIÓN] FASE 1 APROBADA: Perfil completo.")
        
    rejection_reasons.extend(completeness_result['rejections'])
    
    # Si falla completitud básica, retornar temprano
    if rejection_reasons:
        logger.info("🛑 [AGENTE VERIFICACIÓN] Deteniendo validación por fallos en FASE 1.")
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
        
    rejection_reasons.extend(documents_result['rejections'])
    
    # FASE 3: Validaciones de Coherencia (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 3: Analizando coherencia semántica (IA NLP)...")
    coherence_result = validate_coherence(provider_profile, first_service)
    rejection_reasons.extend(coherence_result['rejections'])
    warnings.extend(coherence_result['warnings'])
    if not coherence_result['rejections']:
         logger.info("✅ [AGENTE VERIFICACIÓN] FASE 3 APROBADA: Coherencia validada.")
    
    # FASE 4: Validaciones de Contenido Prohibido (Imágenes) (MOCK)
    logger.info("🔍 [AGENTE VERIFICACIÓN] FASE 4: Moderación de contenido visual (IA Safety)...")
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
    
    # Procesar alertas de seguridad (TODO)
    # if security_alerts:
    #     flag_for_manual_review(provider_profile, security_alerts)
    
    # Determinar resultado
    is_approved = len(rejection_reasons) == 0
    
    if is_approved:
        logger.info("🎉 [AGENTE VERIFICACIÓN] RESULTADO FINAL: APROBADO. El perfil cumple con todos los requisitos.")
    else:
        logger.info(f"🚫 [AGENTE VERIFICACIÓN] RESULTADO FINAL: RECHAZADO. Se encontraron {len(rejection_reasons)} motivos de rechazo.")
    
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
        
        # NLP check for professional content
        logger.info("   - Analizando contenido profesional de la descripción...")
        if MODO_DEBUG: print("   - Analizando contenido profesional de la descripción...")
        prof_check = VerificationHelpers.is_professional_description(description)
        if not prof_check['is_professional']:
            logger.warning(f"   ❌ {prof_check['reason']}")
            if MODO_DEBUG: print(f"   ❌ {prof_check['reason']}")
            rejections.append({
                'code': 'PROFILE_DESCRIPTION_NOT_PROFESSIONAL',
                'message': 'La descripción de tu perfil debe enfocarse en los servicios que ofreces, '
                          'no en características personales. Por favor, describe qué servicios realizas, '
                          'tu experiencia y qué pueden esperar tus clientes.'
            })
        else:
            logger.info("   ✅ Descripción profesional")
            if MODO_DEBUG: print("   ✅ Descripción profesional")
    
    # CRITERIO 3: Coherencia Descripción-Categoría
    if provider_profile.category and description:
        logger.info("   - Validando coherencia descripción-categoría...")
        if MODO_DEBUG: print("   - Validando coherencia descripción-categoría...")
        
        category_match = VerificationHelpers.validate_category_description_match(
            provider_profile.category.name,
            description
        )
        
        if not category_match['is_match']:
            logger.warning(f"   ❌ Descripción no coincide con categoría (similitud: {category_match['similarity']:.2f})")
            if MODO_DEBUG: print(f"   ❌ Descripción no coincide con categoría (similitud: {category_match['similarity']:.2f})")
            rejections.append({
                'code': 'DESCRIPTION_CATEGORY_MISMATCH',
                'message': f'La descripción de tu perfil no parece coincidir con la categoría '
                          f'"{provider_profile.category.name}" que seleccionaste. Por favor, verifica que '
                          f'tu descripción refleje los servicios de esta categoría o selecciona una categoría diferente.'
            })
        else:
            logger.info(f"   ✅ Coherencia categoría-descripción validada (similitud: {category_match['similarity']:.2f})")
            if MODO_DEBUG: print(f"   ✅ Coherencia categoría-descripción validada (similitud: {category_match['similarity']:.2f})")
    
    return {'rejections': rejections}

def validate_identity_documents(provider_profile):
    """
    Valida documentos de identidad (OCR, reconocimiento facial, calidad de imagen).
    NOTA: Ahora usa FieldFiles directamente para soportar Supabase Storage.
    """
    rejections = []
    
    # Verificar que existan los documentos
    logger.info("   - Verificando documentos de identidad (Frontal/Dorso)...")
    if not provider_profile.id_card_front or not provider_profile.id_card_back:
        logger.warning("   ❌ Faltan imágenes de la cédula")
        if MODO_DEBUG: print("   ❌ Faltan imágenes de la cédula")
        rejections.append({
            'code': 'ID_DOCUMENTS_MISSING',
            'message': 'Faltan fotografías de tu cédula de identidad.'
        })
        return {'rejections': rejections}  # No continuar si faltan documentos
    
    logger.info("   ✅ Imágenes de cédula presentes")
    if MODO_DEBUG: print("   ✅ Imágenes de cédula presentes")
    
    # CRITERIO 4: Validar calidad de imágenes de cédula
    # CAMBIO PRINCIPAL: Pasar el FieldFile directamente, no .path
    logger.info("   - Validando calidad de imagen de cédula frontal...")
    if MODO_DEBUG: print("   - Validando calidad de imagen de cédula frontal...")
    
    try:
        # Usar el FieldFile directamente - el helper descargará si es remoto
        front_quality = VerificationHelpers.check_image_quality(provider_profile.id_card_front)
        if not front_quality['is_valid']:
            logger.warning(f"   ❌ Problemas con cédula frontal: {front_quality['issues']}")
            if MODO_DEBUG: print(f"   ❌ Problemas con cédula frontal: {front_quality['issues']}")
            rejections.append({
                'code': 'ID_CARD_FRONT_QUALITY',
                'message': f'La fotografía de tu cédula (frontal) no es lo suficientemente clara. '
                          f'Problemas detectados: {", ".join(front_quality["issues"])}. '
                          f'Por favor, toma una nueva foto con buena iluminación y enfoque.'
            })
        else:
            logger.info("   ✅ Calidad de cédula frontal aceptable")
            if MODO_DEBUG: print("   ✅ Calidad de cédula frontal aceptable")
        
        # Validar cédula posterior
        logger.info("   - Validando calidad de imagen de cédula posterior...")
        if MODO_DEBUG: print("   - Validando calidad de imagen de cédula posterior...")
        
        back_quality = VerificationHelpers.check_image_quality(provider_profile.id_card_back)
        if not back_quality['is_valid']:
            logger.warning(f"   ❌ Problemas con cédula posterior: {back_quality['issues']}")
            if MODO_DEBUG: print(f"   ❌ Problemas con cédula posterior: {back_quality['issues']}")
            rejections.append({
                'code': 'ID_CARD_BACK_QUALITY',
                'message': f'La fotografía de tu cédula (posterior) no es lo suficientemente clara. '
                          f'Problemas detectados: {", ".join(back_quality["issues"])}. '
                          f'Por favor, toma una nueva foto con buena iluminación y enfoque.'
            })
        else:
            logger.info("   ✅ Calidad de cédula posterior aceptable")
            if MODO_DEBUG: print("   ✅ Calidad de cédula posterior aceptable")
    except Exception as e:
        logger.error(f"   ⚠️ Error al validar calidad de imágenes: {e}")
        if MODO_DEBUG: print(f"   ⚠️ Error al validar calidad de imágenes: {e}")
    
    # OCR: Extraer información de la cédula
    logger.info("   - Extrayendo información de cédula (OCR)...")
    if MODO_DEBUG: print("   - Extrayendo información de cédula (OCR)...")
    
    try:
        # Usar FieldFile directamente
        id_info = VerificationHelpers.extract_id_card_info(provider_profile.id_card_front, 'front')
        
        if id_info['success']:
            # Guardar información extraída
            provider_profile.extracted_id_name = id_info.get('name')
            provider_profile.extracted_id_number = id_info.get('id_number')
            provider_profile.extracted_id_expiry = id_info.get('expiry_date')
            provider_profile.save(update_fields=['extracted_id_name', 'extracted_id_number', 'extracted_id_expiry'])
            
            # Validar nombre coincide
            if id_info.get('name'):
                user_full_name = f"{provider_profile.user.first_name} {provider_profile.user.last_name}"
                name_similarity = VerificationHelpers.calculate_name_similarity(
                    id_info['name'], user_full_name
                )
                
                if name_similarity < 0.8:  # 80% similarity threshold
                    logger.warning(f"   ❌ Nombre no coincide: '{id_info['name']}' vs '{user_full_name}' (similitud: {name_similarity:.2f})")
                    if MODO_DEBUG: print(f"   ❌ Nombre no coincide: '{id_info['name']}' vs '{user_full_name}' (similitud: {name_similarity:.2f})")
                    rejections.append({
                        'code': 'ID_NAME_MISMATCH',
                        'message': f'El nombre en tu cédula ({id_info["name"]}) no coincide con el nombre '
                                  f'registrado en tu perfil ({user_full_name}). Por favor, verifica que '
                                  f'los datos de tu perfil coincidan exactamente con tu documento de identidad.'
                    })
                else:
                    logger.info(f"   ✅ Nombre validado (similitud: {name_similarity:.2f})")
                    if MODO_DEBUG: print(f"   ✅ Nombre validado (similitud: {name_similarity:.2f})")
            
            # Validar número de cédula
            if id_info.get('id_number'):
                if not VerificationHelpers.validate_ecuadorian_cedula(id_info['id_number']):
                    logger.warning(f"   ❌ Número de cédula inválido: {id_info['id_number']}")
                    if MODO_DEBUG: print(f"   ❌ Número de cédula inválido: {id_info['id_number']}")
                    rejections.append({
                        'code': 'INVALID_CEDULA_NUMBER',
                        'message': 'El número de cédula extraído no es válido según el algoritmo ecuatoriano.'
                    })
                else:
                    logger.info(f"   ✅ Número de cédula válido: {id_info['id_number']}")
                    if MODO_DEBUG: print(f"   ✅ Número de cédula válido: {id_info['id_number']}")
            
            # Validar fecha de expiración
            if id_info.get('expiry_date'):
                from datetime import date
                if id_info['expiry_date'] < date.today():
                    logger.warning(f"   ❌ Cédula expirada: {id_info['expiry_date']}")
                    if MODO_DEBUG: print(f"   ❌ Cédula expirada: {id_info['expiry_date']}")
                    rejections.append({
                        'code': 'ID_EXPIRED',
                        'message': f'Tu cédula de identidad ha expirado (fecha de expiración: {id_info["expiry_date"]}). '
                                  f'Por favor, actualiza tu documento y sube las nuevas fotografías.'
                    })
                else:
                    logger.info(f"   ✅ Cédula vigente hasta: {id_info['expiry_date']}")
                    if MODO_DEBUG: print(f"   ✅ Cédula vigente hasta: {id_info['expiry_date']}")
        else:
            logger.info("   ℹ️ OCR no disponible o no pudo extraer información (modo mock)")
            if MODO_DEBUG: print("   ℹ️ OCR no disponible o no pudo extraer información (modo mock)")
    except Exception as e:
        logger.error(f"   ⚠️ Error en extracción OCR: {e}")
        if MODO_DEBUG: print(f"   ⚠️ Error en extracción OCR: {e}")
    
    # CRITERIO 5: Verificar selfie con cédula
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
        
        # Validar calidad de selfie - usar FieldFile directamente
        try:
            selfie_quality = VerificationHelpers.check_image_quality(provider_profile.selfie_with_id)
            if not selfie_quality['is_valid']:
                logger.warning(f"   ❌ Problemas con selfie: {selfie_quality['issues']}")
                if MODO_DEBUG: print(f"   ❌ Problemas con selfie: {selfie_quality['issues']}")
                rejections.append({
                    'code': 'SELFIE_QUALITY',
                    'message': f'La calidad de tu selfie de verificación no es suficiente. '
                              f'Problemas: {", ".join(selfie_quality["issues"])}. '
                              f'Por favor, toma una nueva foto con buena iluminación y asegúrate de que '
                              f'tanto tu rostro como tu cédula sean claramente visibles.'
                })
            else:
                logger.info("   ✅ Calidad de selfie aceptable")
                if MODO_DEBUG: print("   ✅ Calidad de selfie aceptable")
                
                # Comparación facial - usar FieldFiles directamente
                logger.info("   - Comparando rostro en selfie vs cédula...")
                if MODO_DEBUG: print("   - Comparando rostro en selfie vs cédula...")
                
                face_comparison = VerificationHelpers.compare_faces(
                    provider_profile.selfie_with_id,
                    provider_profile.id_card_front
                )
                
                provider_profile.facial_match_score = face_comparison['similarity']
                provider_profile.save(update_fields=['facial_match_score'])
                
                if not face_comparison['is_match']:
                    logger.warning(f"   ❌ Rostros no coinciden (similitud: {face_comparison['similarity']:.2f})")
                    if MODO_DEBUG: print(f"   ❌ Rostros no coinciden (similitud: {face_comparison['similarity']:.2f})")
                    rejections.append({
                        'code': 'FACE_MISMATCH',
                        'message': 'El rostro en tu selfie no coincide con la fotografía de tu cédula. '
                                  'Por favor, asegúrate de tomarte la foto tú mismo(a) sosteniendo tu cédula '
                                  'original junto a tu rostro, y que tu rostro sea claramente visible.'
                    })
                else:
                    logger.info(f"   ✅ Verificación facial exitosa (similitud: {face_comparison['similarity']:.2f})")
                    if MODO_DEBUG: print(f"   ✅ Verificación facial exitosa (similitud: {face_comparison['similarity']:.2f})")
        except Exception as e:
            logger.error(f"   ⚠️ Error en verificación de selfie: {e}")
            if MODO_DEBUG: print(f"   ⚠️ Error en verificación de selfie: {e}")
    
    return {'rejections': rejections}

def validate_coherence(provider_profile, service):
    """
    Valida coherencia semántica entre perfil, servicio y categoría.
    """
    rejections = []
    warnings = []
    config = settings.PROVIDER_VERIFICATION_CONFIG
    
    # CRITERIO 6: Servicio relacionado con descripción del perfil
    logger.info("   - Validando coherencia servicio-perfil...")
    if MODO_DEBUG: print("   - Validando coherencia servicio-perfil...")
    
    service_text = f"{service.name} {service.description}"
    profile_desc = provider_profile.description or ""
    
    similarity = VerificationHelpers.calculate_semantic_similarity(service_text, profile_desc)
    threshold = config['semantic_similarity_threshold']
    
    if similarity < threshold:
        logger.warning(f"   ⚠️ Servicio no muy relacionado con perfil (similitud: {similarity:.2f})")
        if MODO_DEBUG: print(f"   ⚠️ Servicio no muy relacionado con perfil (similitud: {similarity:.2f})")
        # Esto es una advertencia, no un rechazo bloqueante
        warnings.append({
            'code': 'SERVICE_PROFILE_LOW_COHERENCE',
            'message': f'Tu servicio "{service.name}" no parece estar muy relacionado con la '
                      f'descripción de tu perfil. Considera actualizar tu descripción de perfil '
                      f'para que refleje mejor los servicios que ofreces.'
        })
    else:
        logger.info(f"   ✅ Coherencia servicio-perfil validada (similitud: {similarity:.2f})")
        if MODO_DEBUG: print(f"   ✅ Coherencia servicio-perfil validada (similitud: {similarity:.2f})")
    
    # CRITERIO 7: Servicio relacionado con categoría
    if provider_profile.category:
        logger.info("   - Validando coherencia servicio-categoría...")
        if MODO_DEBUG: print("   - Validando coherencia servicio-categoría...")
        
        category_match = VerificationHelpers.validate_service_category_match(
            service.name,
            service.description,
            provider_profile.category.name
        )
        
        if not category_match['is_match']:
            logger.warning(f"   ❌ Servicio no coincide con categoría (similitud: {category_match['similarity']:.2f})")
            if MODO_DEBUG: print(f"   ❌ Servicio no coincide con categoría (similitud: {category_match['similarity']:.2f})")
            rejections.append({
                'code': 'SERVICE_CATEGORY_MISMATCH',
                'message': f'Tu servicio "{service.name}" no corresponde a la categoría '
                          f'"{provider_profile.category.name}" que seleccionaste. Por favor, crea un servicio '
                          f'que corresponda a tu categoría o contacta soporte para cambiar de categoría.'
            })
        else:
            logger.info(f"   ✅ Coherencia servicio-categoría validada (similitud: {category_match['similarity']:.2f})")
            if MODO_DEBUG: print(f"   ✅ Coherencia servicio-categoría validada (similitud: {category_match['similarity']:.2f})")
    
    return {'rejections': rejections, 'warnings': warnings}

def validate_image_content(provider_profile, service):
    """
    Valida contenido prohibido en imágenes (contacto, contenido inapropiado).
    NOTA: Ahora usa FieldFiles directamente para soportar Supabase Storage.
    """
    rejections = []
    alerts = []
    config = settings.PROVIDER_VERIFICATION_CONFIG
    
    images_to_check = []
    
    # Recopilar imágenes a verificar - guardar FieldFile, no .path
    if provider_profile.profile_photo:
        images_to_check.append(('profile_photo', provider_profile.profile_photo, 'Foto de perfil'))
    
    if service.image:
        images_to_check.append(('service_image', service.image, 'Imagen del servicio'))
    
    # CRITERIO 8: Sin datos de contacto en imágenes
    logger.info("   - Escaneando imágenes por información de contacto (OCR)...")
    if MODO_DEBUG: print("   - Escaneando imágenes por información de contacto (OCR)...")
    
    for img_type, img_field, img_label in images_to_check:
        try:
            # Usar FieldFile directamente
            contact_result = VerificationHelpers.detect_contact_info_in_image(img_field)
            
            if contact_result['found']:
                logger.warning(f"   ❌ Información de contacto detectada en {img_label}: {contact_result['types']}")
                if MODO_DEBUG: print(f"   ❌ Información de contacto detectada en {img_label}: {contact_result['types']}")
                rejections.append({
                    'code': 'CONTACT_INFO_IN_IMAGE',
                    'message': f'Detectamos información de contacto en tu {img_label} (teléfono, email, '
                              f'redes sociales o página web). Por política de Liberi, las imágenes no '
                              f'pueden contener datos de contacto. Por favor, sube nuevas imágenes sin esta información.'
                })
        except Exception as e:
            logger.warning(f"   ⚠️ Error al escanear {img_label}: {e}")
            if MODO_DEBUG: print(f"   ⚠️ Error al escanear {img_label}: {e}")
    
    # CRITERIO 9: Sin contenido prohibido en imágenes
    logger.info("   - Moderando contenido de imágenes...")
    if MODO_DEBUG: print("   - Moderando contenido de imágenes...")
    
    for img_type, img_field, img_label in images_to_check:
        try:
            # Usar FieldFile directamente
            moderation_result = VerificationHelpers.moderate_image_content(img_field)
            
            if not moderation_result['is_safe']:
                logger.warning(f"   ❌ Contenido inapropiado en {img_label}: {moderation_result['labels']}")
                if MODO_DEBUG: print(f"   ❌ Contenido inapropiado en {img_label}: {moderation_result['labels']}")
                
                # Verificar umbrales específicos
                scores = moderation_result['scores']
                violations = []
                
                if scores.get('nudity', 0) >= config['nudity_threshold']:
                    violations.append('desnudos o contenido sexual')
                if scores.get('violence', 0) >= config['violence_threshold']:
                    violations.append('violencia o armas')
                if scores.get('drugs', 0) >= config['drugs_threshold']:
                    violations.append('drogas')
                
                if violations:
                    rejections.append({
                        'code': 'INAPPROPRIATE_IMAGE_CONTENT',
                        'message': f'Detectamos contenido inapropiado en tu {img_label}: {', '.join(violations)}. '
                                  f'Liberi no permite imágenes que contengan desnudos, contenido sexual, violencia, '
                                  f'armas, drogas o contenido perturbador. Por favor, reemplaza las imágenes con '
                                  f'contenido apropiado y profesional.'
                    })
                    
                    # Alerta de seguridad
                    alerts.append({
                        'type': 'inappropriate_content',
                        'image': img_label,
                        'violations': violations,
                        'scores': scores,
                    })
        except Exception as e:
            logger.warning(f"   ⚠️ Error al moderar {img_label}: {e}")
            if MODO_DEBUG: print(f"   ⚠️ Error al moderar {img_label}: {e}")
    
    if not rejections:
        logger.info("   ✅ Imágenes limpias")
        if MODO_DEBUG: print("   ✅ Imágenes limpias")
    
    return {'rejections': rejections, 'alerts': alerts}

def validate_text_content(provider_profile, service):
    """
    Valida contenido prohibido en texto (contacto, contenido ilegal).
    """
    rejections = []
    alerts = []
    
    # Recopilar textos a verificar
    texts_to_check = [
        ('profile_description', provider_profile.description or '', 'descripción de perfil'),
        ('business_name', provider_profile.business_name or '', 'nombre comercial'),
        ('service_name', service.name, 'nombre del servicio'),
        ('service_description', service.description, 'descripción del servicio'),
    ]
    
    # CRITERIO 10: Sin datos de contacto en texto
    logger.info("   - Escaneando texto por información de contacto...")
    if MODO_DEBUG: print("   - Escaneando texto por información de contacto...")
    
    for text_type, text, text_label in texts_to_check:
        if not text:
            continue
        
        contact_result = VerificationHelpers.detect_contact_info_in_text(text)
        
        if contact_result['found']:
            logger.warning(f"   ❌ Información de contacto en {text_label}: {contact_result['types']}")
            if MODO_DEBUG: print(f"   ❌ Información de contacto en {text_label}: {contact_result['types']}")
            
            contact_types_es = {
                'phone': 'teléfono',
                'email': 'email',
                'url': 'página web',
                'social_media': 'redes sociales'
            }
            
            detected_types = [contact_types_es.get(t, t) for t in contact_result['types']]
            
            rejections.append({
                'code': 'CONTACT_INFO_IN_TEXT',
                'message': f'Tu {text_label} contiene información de contacto ({', '.join(detected_types)}). '
                          f'Por política de Liberi, toda comunicación debe realizarse a través de la plataforma. '
                          f'Por favor, elimina esta información de tus descripciones.'
            })
            break  # Solo reportar una vez
    
    # CRITERIO 11: Sin contenido ilegal o prohibido
    logger.info("   - Escaneando texto por contenido ilegal...")
    if MODO_DEBUG: print("   - Escaneando texto por contenido ilegal...")
    
    for text_type, text, text_label in texts_to_check:
        if not text:
            continue
        
        illegal_result = VerificationHelpers.detect_illegal_content_in_text(text)
        
        if illegal_result['found']:
            logger.error(f"   🚨 CONTENIDO ILEGAL DETECTADO en {text_label}: {illegal_result['categories']}")
            if MODO_DEBUG: print(f"   🚨 CONTENIDO ILEGAL DETECTADO en {text_label}: {illegal_result['categories']}")
            
            rejections.append({
                'code': 'ILLEGAL_CONTENT_DETECTED',
                'message': 'El contenido de tu perfil o servicio contiene referencias a actividades '
                          'ilegales o prohibidas. Liberi es una plataforma para servicios legales '
                          'y profesionales. Tu cuenta ha sido marcada para revisión adicional. '
                          'Si crees que esto es un error, por favor contacta a soporte.'
            })
            
            # Alerta de seguridad CRÍTICA
            alerts.append({
                'type': 'illegal_content',
                'severity': 'CRITICAL',
                'location': text_label,
                'categories': illegal_result['categories'],
                'keywords': illegal_result['keywords'],
                'text_sample': text[:200],  # Primeros 200 caracteres para revisión
            })
            
            break  # Detener al primer contenido ilegal
    
    if not rejections:
        logger.info("   ✅ Texto limpio")
        if MODO_DEBUG: print("   ✅ Texto limpio")
    
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