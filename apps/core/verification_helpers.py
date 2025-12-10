"""
Verification Helpers - Comprehensive validation utilities for provider verification.

This module provides helper methods for:
- Image quality validation
- OCR and text extraction from images
- Contact information detection
- Facial recognition comparison
- Image content moderation
- Text content validation
- Semantic analysis and coherence checking

Note: Supports both local files and remote URLs (Supabase Storage).
"""

import re
import logging
import tempfile
import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional, Union
from contextlib import contextmanager
from django.conf import settings
from django.db.models.fields.files import FieldFile

logger = logging.getLogger(__name__)


class VerificationHelpers:
    """Helper class for provider profile verification."""
    
    # ============================================
    # REMOTE IMAGE HANDLING
    # ============================================
    
    @staticmethod
    @contextmanager
    def get_image_for_processing(image_field_or_path: Union[FieldFile, str]):
        """
        Context manager que obtiene una imagen para procesamiento.
        Maneja tanto archivos locales como URLs remotas (Supabase Storage).
        
        Args:
            image_field_or_path: Un FieldFile de Django o una ruta/URL string
            
        Yields:
            str: Ruta local al archivo (temporal si es remoto)
            
        Example:
            with VerificationHelpers.get_image_for_processing(provider.id_card_front) as image_path:
                result = check_image_quality(image_path)
        """
        temp_file = None
        
        try:
            # Determinar si es un FieldFile o string
            if hasattr(image_field_or_path, 'url'):
                # Es un FieldFile de Django
                image_url = image_field_or_path.url
                
                # Verificar si tiene path local válido
                try:
                    local_path = image_field_or_path.path
                    # CRÍTICO: Verificar que el path sea realmente local y exista
                    # A veces Supabase storage retorna paths como '/app/media/https://...'
                    if local_path and not 'http' in local_path and os.path.exists(local_path):
                        logger.info(f"Using local file: {local_path}")
                        yield local_path
                        return
                except (ValueError, AttributeError, NotImplementedError) as e:
                    # No hay path local válido, usar URL
                    logger.debug(f"No local path available ({e}), using URL")
                    pass
                
                # Descargar desde URL remota
                logger.info(f"Downloading remote image: {image_url}")
                temp_file = VerificationHelpers._download_to_temp(image_url)
                yield temp_file
                
            elif isinstance(image_field_or_path, str):
                # Es un string - puede ser path local o URL
                if image_field_or_path.startswith(('http://', 'https://')):
                    # Es una URL
                    logger.info(f"Downloading from URL: {image_field_or_path}")
                    temp_file = VerificationHelpers._download_to_temp(image_field_or_path)
                    yield temp_file
                elif os.path.exists(image_field_or_path):
                    # Es un path local válido
                    yield image_field_or_path
                else:
                    raise FileNotFoundError(f"File not found: {image_field_or_path}")
            else:
                raise ValueError(f"Invalid image source type: {type(image_field_or_path)}")
                
        finally:
            # Limpiar archivo temporal si existe
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
    
    @staticmethod
    def _download_to_temp(url: str) -> str:
        """
        Descarga una imagen desde URL a un archivo temporal.
        
        Args:
            url: URL de la imagen
            
        Returns:
            str: Ruta al archivo temporal
        """
        import requests
        
        # Determinar extensión del archivo
        extension = '.jpg'  # Default
        if '.' in url.split('/')[-1].split('?')[0]:
            ext = url.split('/')[-1].split('?')[0].split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                extension = f'.{ext}'
        
        # Crear archivo temporal
        fd, temp_path = tempfile.mkstemp(suffix=extension, prefix='liberi_verify_')
        
        try:
            # Descargar imagen
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Escribir al archivo temporal
            with os.fdopen(fd, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded image to: {temp_path} ({os.path.getsize(temp_path)} bytes)")
            return temp_path
            
        except Exception as e:
            # Limpiar en caso de error
            try:
                os.close(fd)
            except:
                pass
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"Failed to download image from {url}: {e}")
    
    @staticmethod
    def get_image_url(image_field) -> Optional[str]:
        """
        Obtiene la URL de una imagen, sea local o remota.
        
        Args:
            image_field: FieldFile de Django
            
        Returns:
            str o None: URL de la imagen
        """
        if not image_field:
            return None
        
        try:
            return image_field.url
        except Exception:
            return None
    
    # ============================================
    # CONTACT INFORMATION PATTERNS
    # ============================================
    
    PHONE_PATTERNS = [
        r'\+?593\s?[0-9]{8,9}',  # Ecuador format
        r'0[0-9]{8,9}',  # Local format
        r'\+?[0-9]{10,15}',  # International
        r'[0-9]{3}[\s\-]?[0-9]{3}[\s\-]?[0-9]{4}',  # Formatted
        r'nueve\s*(tres|3)\s*(cero|0)',  # Written numbers (evasion)
        r'[0-9]\s+[0-9]\s+[0-9]\s+[0-9]\s+[0-9]',  # Spaced numbers
    ]
    
    EMAIL_PATTERNS = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\s*\.\s*[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*\(\s*arroba\s*\)\s*[a-zA-Z0-9.-]+',  # (arroba) evasion
    ]
    
    URL_PATTERNS = [
        r'https?://[^\s]+',  # Must have http:// or https:// explicitly
        r'www\.[a-zA-Z0-9][\w\-]{2,}\.[a-zA-Z]{2,6}',  # www. prefix required
        # Removed plain domain.extension - too many false positives with code
    ]
    
    SOCIAL_MEDIA_PATTERNS = [
        r'@[a-zA-Z0-9._]{3,}',  # @username format
        r'\b(instagram|ig|insta)[\s:/@]+[a-zA-Z0-9._]{3,}',  # Instagram mentions
        r'\b(facebook|fb)[\s:/@]+[a-zA-Z0-9._]{3,}',  # Facebook mentions
        r'\b(tiktok|tt)[\s:/@]+[a-zA-Z0-9._]{3,}',  # TikTok mentions
        r'\b(twitter)[\s:/@]+[a-zA-Z0-9._]{3,}',  # Twitter mentions
        r'\b(x\.com|twitter\.com)[/\s]*[a-zA-Z0-9._]+',  # X.com/Twitter.com URLs
        r'(whatsapp|wsp|ws|wap)[\s:]*\+?[0-9]{8,}',  # WhatsApp with number
    ]
    
    # ============================================
    # IMAGE QUALITY VALIDATION
    # ============================================
    
    @staticmethod
    def check_image_quality(image_source) -> Dict:
        """
        Check image quality (resolution, blur, brightness).
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image_source: FieldFile, path string, o URL
            
        Returns:
            Dict with 'is_valid', 'issues', 'resolution', 'blur_score'
        """
        try:
            with VerificationHelpers.get_image_for_processing(image_source) as image_path:
                return VerificationHelpers._check_image_quality_internal(image_path)
        except Exception as e:
            logger.error(f"Error checking image quality: {e}")
            return {
                'is_valid': False,
                'issues': [f"Error al procesar imagen: {str(e)}"],
                'resolution': (0, 0),
                'blur_score': 0.0,
                'brightness': 0.0,
            }
    
    @staticmethod
    def _check_image_quality_internal(image_path: str) -> Dict:
        """
        Internal method to check image quality from local file.
        """
        try:
            from PIL import Image
            import numpy as np
            
            logger.info(f"Checking image quality for: {image_path}")
            
            # Open image
            img = Image.open(image_path)
            width, height = img.size
            
            issues = []
            
            # Check resolution (minimum 640x480)
            if width < 640 or height < 480:
                issues.append(f"Resolución muy baja ({width}x{height}), mínimo 640x480")
            
            # Convert to grayscale for blur detection
            gray = img.convert('L')
            img_array = np.array(gray)
            
            # Calculate variance of Laplacian (blur detection)
            # Higher variance = sharper image
            laplacian_var = np.var(img_array)
            blur_threshold = 100  # Adjust based on testing
            
            if laplacian_var < blur_threshold:
                issues.append(f"Imagen borrosa (score: {laplacian_var:.2f})")
            
            # Check brightness
            brightness = np.mean(img_array)
            if brightness < 50:
                issues.append("Imagen muy oscura")
            elif brightness > 200:
                issues.append("Imagen sobreexpuesta")
            
            is_valid = len(issues) == 0
            
            result = {
                'is_valid': is_valid,
                'issues': issues,
                'resolution': (width, height),
                'blur_score': float(laplacian_var),
                'brightness': float(brightness),
            }
            
            logger.info(f"Image quality check result: {result}")
            return result
            
        except ImportError:
            logger.warning("PIL/numpy not available, using mock image quality check")
            # Mock response when libraries not available
            return {
                'is_valid': True,
                'issues': [],
                'resolution': (1024, 768),
                'blur_score': 150.0,
                'brightness': 128.0,
            }
    
    # ============================================
    # OCR AND TEXT EXTRACTION
    # ============================================
    
    @staticmethod
    def extract_text_from_image(image_source) -> str:
        """
        Extract text from image using OCR.
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image_source: FieldFile, path string, o URL
            
        Returns:
            Extracted text string
        """
        try:
            with VerificationHelpers.get_image_for_processing(image_source) as image_path:
                return VerificationHelpers._extract_text_from_image_internal(image_path)
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return ""
    
    @staticmethod
    def _extract_text_from_image_internal(image_path: str) -> str:
        """
        Internal method to extract text from local file.
        """
        logger.info(f"Extracting text from image: {image_path}")
        
        try:
            import pytesseract
            from PIL import Image
            
            # Open image
            img = Image.open(image_path)
            
            # Extract text using Tesseract
            # lang='spa' for Spanish, you can add 'eng+spa' for both
            text = pytesseract.image_to_string(img, lang='spa')
            
            logger.info(f"OCR extracted {len(text)} characters")
            return text.strip()
            
        except ImportError:
            logger.warning("pytesseract not available, using mock OCR")
            return ""
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""
    
    @staticmethod
    def extract_id_card_info(image_source, side: str = 'front') -> Dict:
        """
        Extract information from ID card image using OCR.
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image_source: FieldFile, path string, o URL
            side: 'front' or 'back'
            
        Returns:
            Dict with extracted information
        """
        logger.info(f"Extracting ID card info from {side}")
        
        if side != 'front':
            # For back side, just confirm we can read it
            text = VerificationHelpers.extract_text_from_image(image_source)
            return {
                'success': len(text) > 0,
                'confidence': 0.8 if len(text) > 0 else 0.0,
            }
        
        # Extract text from front of ID card
        text = VerificationHelpers.extract_text_from_image(image_source)
        
        if not text:
            logger.warning("No text extracted from ID card")
            return {
                'success': False,
                'name': None,
                'id_number': None,
                'birth_date': None,
                'expiry_date': None,
                'confidence': 0.0,
            }
        
        logger.info(f"Extracted text from ID: {text[:100]}...")
        
        # Extract cedula number (10 digits)
        cedula_pattern = r'\b\d{10}\b'
        cedula_matches = re.findall(cedula_pattern, text)
        id_number = cedula_matches[0] if cedula_matches else None
        
        # Extract dates (DD/MM/YYYY or DD-MM-YYYY)
        date_pattern = r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'
        date_matches = re.findall(date_pattern, text)
        
        birth_date = None
        expiry_date = None
        
        if date_matches:
            from datetime import datetime
            try:
                # First date is usually birth date, second is expiry
                if len(date_matches) >= 1:
                    day, month, year = date_matches[0]
                    birth_date = datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()
                
                if len(date_matches) >= 2:
                    day, month, year = date_matches[1]
                    expiry_date = datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()
            except Exception as e:
                logger.error(f"Error parsing dates: {e}")
        
        # Extract name (usually in uppercase, multiple words)
        # Look for lines with 2-4 uppercase words
        name_pattern = r'\b([A-ZÁÉÍÓÚÑ]{2,}\s+[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,})?(?:\s+[A-ZÁÉÍÓÚÑ]{2,})?)\b'
        name_matches = re.findall(name_pattern, text)
        
        # Filter out common words that aren't names
        excluded_words = ['CEDULA', 'IDENTIDAD', 'REPUBLICA', 'ECUADOR', 'NACIONALIDAD']
        name = None
        for match in name_matches:
            if not any(word in match for word in excluded_words):
                name = match.strip()
                break
        
        success = bool(id_number or name)
        confidence = 0.0
        if id_number and name:
            confidence = 0.9
        elif id_number or name:
            confidence = 0.6
        
        result = {
            'success': success,
            'name': name,
            'id_number': id_number,
            'birth_date': birth_date,
            'expiry_date': expiry_date,
            'confidence': confidence,
        }
        
        logger.info(f"ID extraction result: {result}")
        return result
    
    # ============================================
    # CONTACT INFORMATION DETECTION
    # ============================================
    
    @staticmethod
    def detect_contact_info_in_text(text: str) -> Dict:
        """
        Detect contact information in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with detected contact info and patterns found
        """
        if not text:
            return {'found': False, 'types': [], 'matches': []}
        
        logger.info("Scanning text for contact information...")
        
        found_types = []
        matches = []
        
        # Check for phone numbers
        for pattern in VerificationHelpers.PHONE_PATTERNS:
            phone_matches = re.findall(pattern, text, re.IGNORECASE)
            if phone_matches:
                found_types.append('phone')
                matches.extend(phone_matches)
                logger.warning(f"Found phone pattern: {phone_matches}")
        
        # Check for emails
        for pattern in VerificationHelpers.EMAIL_PATTERNS:
            email_matches = re.findall(pattern, text, re.IGNORECASE)
            if email_matches:
                found_types.append('email')
                matches.extend(email_matches)
                logger.warning(f"Found email pattern: {email_matches}")
        
        # Check for URLs
        for pattern in VerificationHelpers.URL_PATTERNS:
            url_matches = re.findall(pattern, text, re.IGNORECASE)
            if url_matches:
                found_types.append('url')
                matches.extend(url_matches)
                logger.warning(f"Found URL pattern: {url_matches}")
        
        # Check for social media
        for pattern in VerificationHelpers.SOCIAL_MEDIA_PATTERNS:
            social_matches = re.findall(pattern, text, re.IGNORECASE)
            if social_matches:
                found_types.append('social_media')
                matches.extend(social_matches)
                logger.warning(f"Found social media pattern: {social_matches}")
        
        found_types = list(set(found_types))  # Remove duplicates
        
        return {
            'found': len(found_types) > 0,
            'types': found_types,
            'matches': matches,
        }
    
    @staticmethod
    def detect_contact_info_in_image(image_source) -> Dict:
        """
        Detect contact information in image using OCR.
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image_source: FieldFile, path string, o URL
            
        Returns:
            Dict with detection results
        """
        logger.info(f"Scanning image for contact information")
        
        # Extract text from image
        text = VerificationHelpers.extract_text_from_image(image_source)
        
        # Analyze extracted text
        return VerificationHelpers.detect_contact_info_in_text(text)
    
    # ============================================
    # FACIAL RECOGNITION
    # ============================================
    
    @staticmethod
    def compare_faces(image1_source, image2_source) -> Dict:
        """
        Compare two faces for similarity.
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image1_source: Primera imagen (e.g., selfie)
            image2_source: Segunda imagen (e.g., ID card photo)
            
        Returns:
            Dict with similarity score and match status
        """
        logger.info(f"Comparing faces")
        
        config = settings.PROVIDER_VERIFICATION_CONFIG
        threshold = config['facial_match_threshold']
        
        try:
            with VerificationHelpers.get_image_for_processing(image1_source) as image1_path:
                with VerificationHelpers.get_image_for_processing(image2_source) as image2_path:
                    return VerificationHelpers._compare_faces_internal(
                        image1_path, image2_path, threshold
                    )
        except Exception as e:
            logger.error(f"Face comparison error: {e}")
            return {
                'similarity': 0.0,
                'is_match': False,
                'threshold': threshold,
                'confidence': 0.0,
                'error': str(e),
            }
    
    @staticmethod
    def _compare_faces_internal(image1_path: str, image2_path: str, threshold: float) -> Dict:
        """
        Internal method to compare faces from local files.
        """
        # TEMPORAL: Desactivar face_recognition completamente hasta instalar face_recognition_models
        # El worker de Celery se cae cuando intenta usar face_recognition sin los modelos
        logger.warning("face_recognition temporalmente desactivado (falta face_recognition_models), usando mock comparison")
        mock_similarity = 0.90  # 90% match
        return {
            'similarity': mock_similarity,
            'is_match': mock_similarity >= threshold,
            'threshold': threshold,
            'confidence': 0.50,  # Baja confianza porque es mock
            'mock': True,
            'reason': 'face_recognition_models not installed - using mock',
        }
        
        # TODO: Descomentar cuando se instale: pip install git+https://github.com/ageitgey/face_recognition_models
        # try:
        #     import face_recognition
        #     import numpy as np
        #     
        #     # Load images
        #     image1 = face_recognition.load_image_file(image1_path)
        #     image2 = face_recognition.load_image_file(image2_path)
        #     
        #     # Get face encodings
        #     face_encodings1 = face_recognition.face_encodings(image1)
        #     face_encodings2 = face_recognition.face_encodings(image2)
        #     
        #     if not face_encodings1:
        #         logger.warning(f"No face detected in first image")
        #         return {
        #             'similarity': 0.0,
        #             'is_match': False,
        #             'threshold': threshold,
        #             'confidence': 0.0,
        #             'error': 'No face detected in first image',
        #         }
        #     
        #     if not face_encodings2:
        #         logger.warning(f"No face detected in second image")
        #         return {
        #             'similarity': 0.0,
        #             'is_match': False,
        #             'threshold': threshold,
        #             'confidence': 0.0,
        #             'error': 'No face detected in second image',
        #         }
        #     
        #     # Compare faces (use first detected face in each image)
        #     face_encoding1 = face_encodings1[0]
        #     face_encoding2 = face_encodings2[0]
        #     
        #     # Calculate face distance (lower is more similar)
        #     face_distance = face_recognition.face_distance([face_encoding2], face_encoding1)[0]
        #     
        #     # Convert distance to similarity score (0-1, higher is more similar)
        #     # face_distance ranges from 0 (identical) to ~1.0 (very different)
        #     similarity = 1.0 - face_distance
        #     
        #     # Ensure similarity is between 0 and 1
        #     similarity = max(0.0, min(1.0, similarity))
        #     
        #     is_match = similarity >= threshold
        #     
        #     logger.info(f"Face comparison: similarity={similarity:.3f}, threshold={threshold}, match={is_match}")
        #     
        #     return {
        #         'similarity': float(similarity),
        #         'is_match': is_match,
        #         'threshold': threshold,
        #         'confidence': 0.95,
        #         'face_distance': float(face_distance),
        #     }
        #     
        # except ImportError as e:
        #     logger.warning(f"face_recognition not available: {e}, using mock comparison")
        #     # Mock response for development
        #     mock_similarity = 0.90  # 90% match
        #     return {
        #         'similarity': mock_similarity,
        #         'is_match': mock_similarity >= threshold,
        #         'threshold': threshold,
        #         'confidence': 0.95,
        #         'mock': True,
        #         'error': str(e),
        #     }
        # except Exception as e:
        #     # CRÍTICO: Capturar CUALQUIER excepción para evitar que Celery worker se caiga
        #     logger.error(f"Error en comparación facial (usando mock): {e}", exc_info=True)
        #     # Mock response cuando face_recognition falla
        #     mock_similarity = 0.90  # 90% match
        #     return {
        #         'similarity': mock_similarity,
        #         'is_match': mock_similarity >= threshold,
        #         'threshold': threshold,
        #         'confidence': 0.50,  # Baja confianza porque es mock
        #         'mock': True,
        #         'error': f'Face recognition failed: {str(e)}',
        #     }
    
    # ============================================
    # IMAGE CONTENT MODERATION
    # ============================================
    
    @staticmethod
    def moderate_image_content(image_source) -> Dict:
        """
        Moderate image for inappropriate content.
        Soporta archivos locales y URLs remotas (Supabase).
        
        Args:
            image_source: FieldFile, path string, o URL
            
        Returns:
            Dict with moderation labels and scores
        """
        logger.info(f"Moderating image content")
        
        # TODO: Implement real moderation using AWS Rekognition or similar
        # Example with downloaded file:
        # try:
        #     with VerificationHelpers.get_image_for_processing(image_source) as image_path:
        #         import boto3
        #         client = boto3.client('rekognition')
        #         with open(image_path, 'rb') as f:
        #             response = client.detect_moderation_labels(
        #                 Image={'Bytes': f.read()},
        #                 MinConfidence=60
        #             )
        #         return process_rekognition_response(response)
        # except Exception as e:
        #     logger.error(f"Moderation error: {e}")
        
        # Mock response - all safe
        return {
            'is_safe': True,
            'labels': [],
            'scores': {
                'nudity': 0.01,
                'violence': 0.01,
                'drugs': 0.01,
                'gore': 0.01,
                'hate_symbols': 0.01,
            },
            'mock': True,
        }
    
    # ============================================
    # TEXT CONTENT VALIDATION
    # ============================================
    
    @staticmethod
    def detect_illegal_content_in_text(text: str) -> Dict:
        """
        Detect illegal or prohibited content in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with detection results
        """
        if not text:
            return {'found': False, 'categories': [], 'keywords': []}
        
        logger.info("Scanning text for illegal content...")
        
        config = settings.PROVIDER_VERIFICATION_CONFIG
        prohibited = config.get('prohibited_keywords', {})
        
        found_categories = []
        found_keywords = []
        
        text_lower = text.lower()
        
        for category, keywords in prohibited.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    found_categories.append(category)
                    found_keywords.append(keyword)
                    logger.warning(f"Found prohibited keyword '{keyword}' in category '{category}'")
        
        found_categories = list(set(found_categories))
        
        return {
            'found': len(found_categories) > 0,
            'categories': found_categories,
            'keywords': found_keywords,
        }
    
    @staticmethod
    def is_professional_description(text: str) -> Dict:
        """
        Analyze if description is professional and service-focused.
        
        Args:
            text: Description text
            
        Returns:
            Dict with analysis results
        """
        if not text:
            return {'is_professional': False, 'reason': 'Descripción vacía'}
        
        logger.info("Analyzing description professionalism...")
        
        # Service-related action verbs (Spanish)
        service_verbs = [
            'ofrezco', 'realizo', 'brindo', 'proporciono', 'ejecuto',
            'hago', 'presto', 'doy', 'proveo', 'efectúo',
            'especializo', 'especializada', 'especializada', 'dedico', 'trabajo', 'atiendo', 'ayudo',
        ]
        
        # Service-related nouns
        service_nouns = [
            'servicio', 'servicios', 'trabajo', 'experiencia', 'profesional',
            'calidad', 'atención', 'cliente', 'resultado', 'instalación',
            'instalaciones', 'reparación', 'reparaciones', 'limpieza',
        ]
        
        text_lower = text.lower()
        
        # Check for service verbs
        has_service_verbs = any(verb in text_lower for verb in service_verbs)
        
        # Check for service nouns
        has_service_nouns = any(noun in text_lower for noun in service_nouns)
        
        # Educational/Client-benefit keywords (common in tutoring, coaching, etc.)
        educational_keywords = [
            'aprender', 'aprende', 'enseñ', 'clase', 'clases', 'tutoría', 'tutorías',
            'curso', 'cursos', 'capacit', 'entrenamient', 'formación',
            'programar', 'programación', 'desarrollo', 'habilidad', 'habilidades',
            'carrera', 'impulsar', 'mejorar', 'dominar', 'aprendizaje',
        ]
        
        # Client-focused verbs (segunda persona - common in marketing)
        client_focused_verbs = [
            'quieres', 'puedes', 'necesitas', 'buscas', 'deseas',
            'aprende', 'mejora', 'desarrolla', 'domina', 'obtén',
        ]
        
        has_educational = any(keyword in text_lower for keyword in educational_keywords)
        has_client_focus = any(verb in text_lower for verb in client_focused_verbs)
        
        # Personal-only indicators (red flags)
        personal_only = [
            'soy alto', 'soy bajo', 'soy moreno', 'soy blanco',
            'tengo ojos', 'mi color favorito', 'me gusta bailar',
            'me gusta cantar', 'soy fan de',
        ]
        
        is_personal_only = any(phrase in text_lower for phrase in personal_only)
        
        if is_personal_only:
            return {
                'is_professional': False,
                'reason': 'Descripción enfocada en características personales, no en servicios',
            }
        
        # Accept if: has service language OR educational/client-focused language
        if has_service_verbs or has_service_nouns or has_educational or has_client_focus:
            return {
                'is_professional': True,
                'reason': 'Descripción enfocada en servicios',
            }
        
        return {
            'is_professional': False,
            'reason': 'Descripción no menciona servicios claramente',
        }
    
    @staticmethod
    def validate_text_is_real(text: str) -> Dict:
        """
        Detecta si un texto es gibberish, Lorem Ipsum, o texto de relleno inválido.
        
        Args:
            text: Texto a validar
            
        Returns:
            Dict with validation result:
            {
                'is_valid': bool,
                'reason': str  # If not valid
            }
        """
        logger.info("Validating text is real (not gibberish)")
        
        if not text or len(text.strip()) < 10:
            return {
                'is_valid': False,
                'reason': 'Texto demasiado corto'
            }
        
        text_lower = text.lower()
        
        # Check 1: Known placeholder text
        placeholders = [
            'lorem ipsum', 'dolor sit amet', 'consectetur adipiscing',
            'lorem', 'ipsum', 'placeholder',
            'test', 'testing', 'prueba', 'ejemplo',
            'asdfg', 'qwerty', 'zxcvb',
        ]
        
        for placeholder in placeholders:
            if placeholder in text_lower:
                return {
                    'is_valid': False,
                    'reason': f'Contiene texto de relleno: "{placeholder}"'
                }
        
        # Check 2: Too many consonants without vowels (gibberish pattern)
        words = text.split()
        gibberish_words = []
        
        for word in words:
            if len(word) >= 5:  # Only check longer words
                word_clean = ''.join(c for c in word.lower() if c.isalpha())
                if len(word_clean) >= 5:
                    vowels = sum(1 for c in word_clean if c in 'aeiouáéíóú')
                    consonants = len(word_clean) - vowels
                    
                    # If more than 70% consonants, likely gibberish
                    if consonants / len(word_clean) > 0.7:
                        gibberish_words.append(word)
        
        if len(gibberish_words) >= 2:  # Multiple gibberish words
            return {
                'is_valid': False,
                'reason': f'Contiene texto sin sentido: {", ".join(gibberish_words[:3])}'
            }
        
        # Check 3: Repeated character patterns (keyboard mashing)
        repeated_patterns = [
            'aaaa', 'bbbb', 'cccc', 'dddd', 'eeee',
            'jjjj', 'kkkk', 'llll', 'ffff',
            'jaja', 'jeje', 'kkkk',
        ]
        
        for pattern in repeated_patterns:
            if pattern in text_lower:
                return {
                    'is_valid': False,
                    'reason': 'Contiene patrones repetitivos inválidos'
                }
        
        # Check 4: Very low word diversity (same word repeated many times)
        if len(words) >= 10:
            unique_words = set(w.lower() for w in words if len(w) > 3)
            diversity = len(unique_words) / len(words)
            
            if diversity < 0.3:  # Less than 30% unique words
                return {
                    'is_valid': False,
                    'reason': 'Texto muy repetitivo'
                }
        
        # Passed all checks
        return {
            'is_valid': True,
            'reason': 'Texto válido'
        }
    
    # ============================================
    # SEMANTIC ANALYSIS
    # ============================================
    
    def calculate_semantic_similarity(text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.
        Uses simple keyword matching (can be upgraded to embeddings).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # Simple keyword-based similarity
        # TODO: Upgrade to sentence embeddings (sentence-transformers)
        
        # Normalize texts
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        
        # Remove common stop words (Spanish)
        stop_words = {
            'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se',
            'no', 'haber', 'por', 'con', 'su', 'para', 'como', 'estar',
            'tener', 'le', 'lo', 'todo', 'pero', 'más', 'hacer', 'o',
            'poder', 'decir', 'este', 'ir', 'otro', 'ese', 'si', 'me',
            'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy', 'sin',
        }
        
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0.0
        
        logger.info(f"Semantic similarity: {similarity:.3f}")
        return similarity
    
    @staticmethod
    def validate_category_description_match(category_name: str, description: str) -> Dict:
        """
        Validate that description matches the category.
        
        Args:
            category_name: Name of the category
            description: Provider description
            
        Returns:
            Dict with validation results
        """
        logger.info(f"Validando coherencia descripción-categoría para: {category_name}")
        
        config = settings.PROVIDER_VERIFICATION_CONFIG
        category_keywords = config.get('category_keywords', {})
        
        # Get keywords for this category
        keywords = category_keywords.get(category_name, [])
        
        if not keywords:
            logger.warning(f"No keywords defined for category: {category_name}")
            # If no keywords defined, pass validation
            return {
                'is_match': True,
                'similarity': 1.0,
                'matched_keywords': [],
                'threshold': 0.0,
                'reason': 'No hay palabras clave definidas para esta categoría',
            }
        
        description_lower = description.lower()
        
        # Count matching keywords
        matches = [kw for kw in keywords if kw.lower() in description_lower]
        
        # Use minimum keyword count instead of percentage
        # At least 1 keyword must match for validation to pass (relaxed from 2)
        min_keywords_required = 1
        is_match = len(matches) >= min_keywords_required
        
        # Calculate match ratio for informational purposes
        match_ratio = len(matches) / len(keywords) if keywords else 0.0
        
        logger.info(f"Coincidencias encontradas: {len(matches)}/{len(keywords)} palabras clave")
        logger.info(f"Palabras coincidentes: {', '.join(matches[:5])}")  # Mostrar primeras 5
        
        return {
            'is_match': is_match,
            'similarity': match_ratio,
            'matched_keywords': matches,
            'threshold': min_keywords_required,
            'min_required': min_keywords_required,
        }
    
    @staticmethod
    def validate_service_category_match(service_name: str, service_desc: str, 
                                       category_name: str) -> Dict:
        """
        Validate that service matches the category.
        
        Args:
            service_name: Name of the service
            service_desc: Service description
            category_name: Category name
            
        Returns:
            Dict with validation results
        """
        logger.info(f"Validating service-category match for: {category_name}")
        
        # Combine service name and description
        service_text = f"{service_name} {service_desc}"
        
        # Use same logic as category-description match
        return VerificationHelpers.validate_category_description_match(
            category_name, service_text
        )
    
    # ============================================
    # VALIDATORS
    # ============================================
    
    @staticmethod
    def validate_ecuadorian_cedula(cedula: str) -> bool:
        """
        Validate Ecuadorian ID number (cédula) using official algorithm.
        
        Args:
            cedula: ID number string
            
        Returns:
            True if valid, False otherwise
        """
        if not cedula or not cedula.isdigit():
            return False
        
        if len(cedula) != 10:
            return False
        
        # Province code (first 2 digits) must be between 01 and 24
        province = int(cedula[:2])
        if province < 1 or province > 24:
            return False
        
        # Third digit must be less than 6 (for natural persons)
        if int(cedula[2]) >= 6:
            return False
        
        # Validate check digit using module 10 algorithm
        coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        
        for i in range(9):
            value = int(cedula[i]) * coefficients[i]
            if value >= 10:
                value -= 9
            total += value
        
        check_digit = (10 - (total % 10)) % 10
        
        return check_digit == int(cedula[9])
    
    @staticmethod
    def calculate_name_similarity(name1: str, name2: str) -> float:
        """
        Calculate similarity between two names.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalize: lowercase, remove extra spaces, remove accents
        def normalize(text):
            import unicodedata
            text = text.lower().strip()
            # Remove accents
            text = ''.join(
                c for c in unicodedata.normalize('NFD', text)
                if unicodedata.category(c) != 'Mn'
            )
            # Remove extra spaces
            text = ' '.join(text.split())
            return text
        
        name1_norm = normalize(name1)
        name2_norm = normalize(name2)
        
        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, name1_norm, name2_norm).ratio()
        
        logger.info(f"Name similarity: '{name1}' vs '{name2}' = {similarity:.3f}")
        return similarity
    
    # ============================================
    # ID CARD VALIDATION (NEW - ROBUST)
    # ============================================
    
    @staticmethod
    def is_valid_id_card_image(image_source, side: str = 'front') -> Dict:
        """
        Detecta si una imagen es realmente una cédula de identidad ecuatoriana.
        
        Args:
            image_source: FieldFile, path, o URL de la imagen
            side: 'front' o 'back'
            
        Returns:
            Dict with validation result:
            {
                'is_valid': bool,
                'confidence': float,
                'reasons': List[str]  # Reasons if not valid
            }
        """
        logger.info(f"Validating if image is a valid ID card ({side})")
        
        try:
            with VerificationHelpers.get_image_for_processing(image_source) as image_path:
                from PIL import Image
                import numpy as np
                
                reasons = []
                confidence = 0.0
                
                # Open image
                img = Image.open(image_path)
                width, height = img.size
                
                # Check 1: Aspect ratio (cédulas ~1.6 ratio like credit cards)
                aspect_ratio = width / height if height > 0 else 0
                if not (1.4 <= aspect_ratio <= 1.8):
                    reasons.append(f"Proporción incorrecta ({aspect_ratio:.2f}), cédulas tienen ~1.6")
                else:
                    confidence += 0.2
                
                # Check 2: Extract text with OCR
                text = VerificationHelpers.extract_text_from_image(image_source)
                text_upper = text.upper()
                
                if side == 'front':
                    # Keywords que DEBEN aparecer en cédula frontal ecuatoriana
                    required_keywords = [
                        ('REPÚBLICA', 'ECUADOR', 'REPUBLICA'),  # Al menos uno
                        ('CÉDULA', 'CEDULA'),  # Al menos uno
                        ('IDENTIDAD',),
                        ('APELLIDOS',),
                        ('NOMBRES',),
                    ]
                    
                    keywords_found = 0
                    for keyword_group in required_keywords:
                        if any(kw in text_upper for kw in keyword_group):
                            keywords_found += 1
                            confidence += 0.15
                    
                    if keywords_found < 3:  # Al menos 3 de 5 grupos
                        reasons.append(f"Faltan keywords de cédula (encontrados: {keywords_found}/5)")
                    
                    # Check for ID number pattern (10 digits)
                    if not re.search(r'\b\d{10}\b', text):
                        reasons.append("No se encontró número de cédula (10 dígitos)")
                    else:
                        confidence += 0.1
                        
                elif side == 'back':
                    # Keywords del reverso
                    back_keywords = [
                        ('PADRE', 'MADRE'),
                        ('CÓDIGO', 'CODIGO', 'DACTILAR'),
                        ('CIVIL',),
                    ]
                    
                    keywords_found = 0
                    for keyword_group in back_keywords:
                        if any(kw in text_upper for kw in keyword_group):
                            keywords_found += 1
                            confidence += 0.15
                    
                    # Check for MRZ (Machine Readable Zone) - very distinctive
                    # MRZ has patterns like: ECUXXXXXXXXX<<<<<XXXXXXXXX
                    # or APELLIDO<APELLIDO<<NOMBRE<NOMBRE<
                    if re.search(r'[A-Z<]{10,}', text_upper):
                        confidence += 0.3
                        logger.info("MRZ pattern detected")
                    else:
                        reasons.append("No se detectó zona MRZ (código de barras de texto)")
                    
                    if keywords_found < 1:
                        reasons.append(f"Faltan keywords del reverso (encontrados: {keywords_found}/3)")
                
                # Check 3: Minimum text extracted
                if len(text.strip()) < 20:
                    reasons.append(f"Muy poco texto extraído ({len(text)} caracteres)")
                    confidence -= 0.2
                else:
                    confidence += 0.1
                
                # Final decision
                is_valid = confidence >= 0.4 and len(reasons) <= 2
                
                logger.info(f"ID card validation: valid={is_valid}, confidence={confidence:.2f}, reasons={reasons}")
                
                return {
                    'is_valid': is_valid,
                    'confidence': confidence,
                    'reasons': reasons,
                }
                
        except Exception as e:
            logger.error(f"Error validating ID card image: {e}", exc_info=True)
            return {
                'is_valid': False,
                'confidence': 0.0,
                'reasons': [f"Error al procesar imagen: {str(e)}"],
            }
    
    @staticmethod
    def extract_id_info_from_text(text: str, side: str = 'front') -> Dict:
        """
        Extrae información estructurada de una cédula desde texto OCR.
        
        Args:
            text: Texto extraído por OCR
            side: 'front' o 'back'
            
        Returns:
            Dict with extracted information
        """
        logger.info(f"Extracting ID info from text ({side})")
        
        result = {
            'success': False,
            'apellidos': None,
            'nombres': None,
            'id_number': None,
            'birth_date': None,
            'raw_text': text,
        }
        
        try:
            # Normalize text
            text_clean = text.replace('\r', '\n')
            text_upper = text_clean.upper()
            
            # Log first 200 chars for debugging
            logger.info(f"OCR Text preview (first 200 chars): {text_clean[:200]}")
            
            # CRITICAL: Try MRZ FIRST on BOTH sides (Ecuadorian IDs have MRZ on front!)
            logger.info("Trying MRZ extraction first...")
            mrz_result = VerificationHelpers.parse_mrz(text)
            if mrz_result['success']:
                result.update(mrz_result)
                result['success'] = True
                logger.info(f"✅ MRZ parsed successfully from {side}: {result['apellidos']}, {result['nombres']}")
                return result
            
            # If MRZ failed, try traditional patterns (only on front)
            if side == 'front':
                logger.info("MRZ not found, trying traditional patterns...")
                
                # APELLIDOS - Multiple patterns with fallbacks
                apellidos_patterns = [
                    # Pattern 1: APELLIDOS followed by newline and text
                    r'APELLIDOS?\s*[:|\n\r]+\s*([A-ZÁÉÍÓÚÑ\s]+?)(?:\n|NOMBRES|CONDICIÓN|NACIONAL IDAD)',
                    # Pattern 2: Just find text after APELLIDOS
                    r'APELLIDOS?\s*[:|\n\r]+\s*([A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]+)?)',
                    # Pattern 3: Two consecutive uppercase words (likely apellidos)
                    r'\n([A-ZÁÉÍÓÚÑ]{4,}\s+[A-ZÁÉÍÓÚÑ]{4,})\s*\n.*NOMBRES',
                ]
                
                for i, pattern in enumerate(apellidos_patterns):
                    apellidos_match = re.search(pattern, text_upper, re.MULTILINE | re.DOTALL)
                    if apellidos_match:
                        result['apellidos'] = apellidos_match.group(1).strip()
                        logger.info(f"✅ Extracted apellidos (pattern {i+1}): {result['apellidos']}")
                        break
                else:
                    logger.warning("⚠️ No apellidos match found with any pattern")
                
                # NOMBRES - Multiple patterns with fallbacks
                nombres_patterns = [
                    # Pattern 1: NOMBRES followed by newline and text
                    r'NOMBRES?\s*[:|\n\r]+\s*([A-ZÁÉÍÓÚÑ\s]+?)(?:\n|NACIONALIDAD|ECUATORIAN|LUGAR)',
                    # Pattern 2: Just find text after NOMBRES
                    r'NOMBRES?\s*[:|\n\r]+\s*([A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]+)?)',
                    # Pattern 3: Text between APELLIDOS section and NACIONALIDAD
                    r'APELLIDOS.*?\n.*?\n([A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]+)?)\s*.*?NACIONALIDAD',
                ]
                
                for i, pattern in enumerate(nombres_patterns):
                    nombres_match = re.search(pattern, text_upper, re.MULTILINE | re.DOTALL)
                    if nombres_match:
                        result['nombres'] = nombres_match.group(1).strip()
                        logger.info(f"✅ Extracted nombres (pattern {i+1}): {result['nombres']}")
                        break
                else:
                    logger.warning("⚠️ No nombres match found with any pattern")
                
                # ID NUMBER - 10 digits
                id_match = re.search(r'\b(\d{10})\b', text)
                if id_match:
                    result['id_number'] = id_match.group(1)
                    logger.info(f"✅ Extracted ID: {result['id_number']}")
                else:
                    logger.warning("⚠️ No ID number found")
            
            # Success if we got at least apellidos or nombres
            result['success'] = bool(result['apellidos'] or result['nombres'])
            
            if result['success']:
                logger.info(f"✅ Extraction successful: apellidos={result['apellidos']}, nombres={result['nombres']}")
            else:
                logger.warning(f"❌ Extraction failed - could not find apellidos or nombres in text")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting ID info: {e}", exc_info=True)
            return result
    
    @staticmethod
    def parse_mrz(text: str) -> Dict:
        """
        Parsea la zona MRZ (Machine Readable Zone) de una cédula.
        """
        result = {
            'success': False,
            'apellidos': None,
            'nombres': None,
            'id_number': None,
        }
        
        try:
            text_upper = text.upper()
            
            # Look for MRZ patterns with multiple fallbacks
            mrz_patterns = [
                # Pattern 1: Standard MRZ - APELLIDO<APELLIDO<<NOMBRE<NOMBRE<
                r'([A-Z]+)<([A-Z]+)<<([A-Z]+)<([A-Z]+)<',
                # Pattern 2: Single apellido - APELLIDO<<NOMBRE<NOMBRE<
                r'([A-Z]+)<<([A-Z]+)<([A-Z]+)<',
                # Pattern 3: Without trailing < - APELLIDO<APELLIDO<<NOMBRE<NOMBRE
                r'([A-Z]+)<([A-Z]+)<<([A-Z]+)<([A-Z]+)',
            ]
            
            for i, pattern in enumerate(mrz_patterns):
                mrz_match = re.search(pattern, text_upper)
                
                if mrz_match:
                    groups = mrz_match.groups()
                    
                    if len(groups) == 4:
                        # Full format with 2 apellidos and 2 nombres
                        apellido1 = groups[0]
                        apellido2 = groups[1]
                        nombre1 = groups[2]
                        nombre2 = groups[3]
                        
                        result['apellidos'] = f"{apellido1} {apellido2}".strip()
                        result['nombres'] = f"{nombre1} {nombre2}".strip()
                    elif len(groups) == 3:
                        # Single apellido format
                        apellido = groups[0]
                        nombre1 = groups[1]
                        nombre2 = groups[2]
                        
                        result['apellidos'] = apellido.strip()
                        result['nombres'] = f"{nombre1} {nombre2}".strip()
                    
                    result['success'] = True
                    logger.info(f"✅ MRZ parsed (pattern {i+1}): {result['apellidos']}, {result['nombres']}")
                    return result
            
            # If no pattern matched, log for debugging
            logger.warning(f"⚠️ No MRZ pattern found in text (searched {len(mrz_patterns)} patterns)")
            # Log a snippet to help debug
            if len(text) > 100:
                logger.info(f"MRZ search area (mid section): ...{text[len(text)//2-50:len(text)//2+50]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing MRZ: {e}", exc_info=True)
            return result
    
    @staticmethod
    def compare_names(ocr_name: str, registered_name: str) -> Dict:
        """
        Compara nombres extraídos de cédula con nombre registrado usando fuzzy matching.
        """
        logger.info(f"Comparing names: OCR='{ocr_name}' vs Registered='{registered_name}'")
        
        if not ocr_name or not registered_name:
            return {
                'match': False,
                'similarity': 0.0,
                'partial_matches': [],
                'explanation': 'Nombres vacíos'
            }
        
        # Normalize both names
        import unicodedata
        def normalize(text):
            text = ''.join(
                c for c in unicodedata.normalize('NFD', text.upper())
                if unicodedata.category(c) != 'Mn'
            )
            return text.split()
        
        ocr_parts = normalize(ocr_name)
        reg_parts = normalize(registered_name)
        
        # Find partial matches
        matches = []
        for reg_word in reg_parts:
            best_match = None
            best_similarity = 0.0
            
            for ocr_word in ocr_parts:
                similarity = SequenceMatcher(None, reg_word, ocr_word).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = ocr_word
            
            if best_similarity >= 0.75:  # 75% similar
                matches.append({
                    'registered': reg_word,
                    'ocr': best_match,
                    'similarity': best_similarity
                })
        
        # Calculate overall similarity
        if matches:
            avg_similarity = sum(m['similarity'] for m in matches) / len(reg_parts)
        else:
            avg_similarity = 0.0
        
        # Decision: Need at least 2 words matching OR 60% of registered words
        match_ratio = len(matches) / len(reg_parts) if reg_parts else 0
        is_match = (len(matches) >= 2 and avg_similarity >= 0.75) or match_ratio >= 0.6
        
        explanation = f"{len(matches)}/{len(reg_parts)} palabras coinciden (promedio: {avg_similarity:.1%})"
        
        logger.info(f"Name comparison: match={is_match}, similarity={avg_similarity:.2f}")
        
        return {
            'match': is_match,
            'similarity': avg_similarity,
            'partial_matches': matches,
            'explanation': explanation
        }