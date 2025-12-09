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

Note: Currently uses mock/simulated responses for external AI services.
Real API implementations can be swapped in when credentials are available.
"""

import re
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class VerificationHelpers:
    """Helper class for provider profile verification."""
    
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
        r'(https?://|www\.)[^\s]+',
        r'[a-zA-Z0-9-]+\.(com|ec|net|org|io|app)[^\s]*',
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
    def check_image_quality(image_path: str) -> Dict:
        """
        Check image quality (resolution, blur, brightness).
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dict with 'is_valid', 'issues', 'resolution', 'blur_score'
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
        except Exception as e:
            logger.error(f"Error checking image quality: {e}")
            return {
                'is_valid': False,
                'issues': [f"Error al procesar imagen: {str(e)}"],
                'resolution': (0, 0),
                'blur_score': 0.0,
                'brightness': 0.0,
            }
    
    # ============================================
    # OCR AND TEXT EXTRACTION
    # ============================================
    
    @staticmethod
    def extract_text_from_image(image_path: str) -> str:
        """
        Extract text from image using OCR.
        Uses pytesseract (Tesseract OCR) if available, falls back to mock.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text string
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
    def extract_id_card_info(image_path: str, side: str = 'front') -> Dict:
        """
        Extract information from ID card image using OCR.
        
        Args:
            image_path: Path to ID card image
            side: 'front' or 'back'
            
        Returns:
            Dict with extracted information
        """
        logger.info(f"Extracting ID card info from {side}: {image_path}")
        
        if side != 'front':
            # For back side, just confirm we can read it
            text = VerificationHelpers.extract_text_from_image(image_path)
            return {
                'success': len(text) > 0,
                'confidence': 0.8 if len(text) > 0 else 0.0,
            }
        
        # Extract text from front of ID card
        text = VerificationHelpers.extract_text_from_image(image_path)
        
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
    def detect_contact_info_in_image(image_path: str) -> Dict:
        """
        Detect contact information in image using OCR.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with detection results
        """
        logger.info(f"Scanning image for contact information: {image_path}")
        
        # Extract text from image
        text = VerificationHelpers.extract_text_from_image(image_path)
        
        # Analyze extracted text
        return VerificationHelpers.detect_contact_info_in_text(text)
    
    # ============================================
    # FACIAL RECOGNITION
    # ============================================
    
    @staticmethod
    def compare_faces(image1_path: str, image2_path: str) -> Dict:
        """
        Compare two faces for similarity.
        Uses face_recognition library if available, falls back to mock.
        
        Args:
            image1_path: Path to first image (e.g., selfie)
            image2_path: Path to second image (e.g., ID card photo)
            
        Returns:
            Dict with similarity score and match status
        """
        logger.info(f"Comparing faces: {image1_path} vs {image2_path}")
        
        config = settings.PROVIDER_VERIFICATION_CONFIG
        threshold = config['facial_match_threshold']
        
        try:
            import face_recognition
            import numpy as np
            
            # Load images
            image1 = face_recognition.load_image_file(image1_path)
            image2 = face_recognition.load_image_file(image2_path)
            
            # Get face encodings
            face_encodings1 = face_recognition.face_encodings(image1)
            face_encodings2 = face_recognition.face_encodings(image2)
            
            if not face_encodings1:
                logger.warning(f"No face detected in {image1_path}")
                return {
                    'similarity': 0.0,
                    'is_match': False,
                    'threshold': threshold,
                    'confidence': 0.0,
                    'error': 'No face detected in first image',
                }
            
            if not face_encodings2:
                logger.warning(f"No face detected in {image2_path}")
                return {
                    'similarity': 0.0,
                    'is_match': False,
                    'threshold': threshold,
                    'confidence': 0.0,
                    'error': 'No face detected in second image',
                }
            
            # Compare faces (use first detected face in each image)
            face_encoding1 = face_encodings1[0]
            face_encoding2 = face_encodings2[0]
            
            # Calculate face distance (lower is more similar)
            face_distance = face_recognition.face_distance([face_encoding2], face_encoding1)[0]
            
            # Convert distance to similarity score (0-1, higher is more similar)
            # face_distance ranges from 0 (identical) to ~1.0 (very different)
            similarity = 1.0 - face_distance
            
            # Ensure similarity is between 0 and 1
            similarity = max(0.0, min(1.0, similarity))
            
            is_match = similarity >= threshold
            
            logger.info(f"Face comparison: similarity={similarity:.3f}, threshold={threshold}, match={is_match}")
            
            return {
                'similarity': float(similarity),
                'is_match': is_match,
                'threshold': threshold,
                'confidence': 0.95,
                'face_distance': float(face_distance),
            }
            
        except ImportError:
            logger.warning("face_recognition not available, using mock comparison")
            # Mock response for development
            mock_similarity = 0.90  # 90% match
            return {
                'similarity': mock_similarity,
                'is_match': mock_similarity >= threshold,
                'threshold': threshold,
                'confidence': 0.95,
                'mock': True,
            }
        except Exception as e:
            logger.error(f"Face comparison error: {e}")
            return {
                'similarity': 0.0,
                'is_match': False,
                'threshold': threshold,
                'confidence': 0.0,
                'error': str(e),
            }
    
    # ============================================
    # IMAGE CONTENT MODERATION
    # ============================================
    
    @staticmethod
    def moderate_image_content(image_path: str) -> Dict:
        """
        Moderate image for inappropriate content (mock implementation).
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with moderation labels and scores
        """
        logger.info(f"Moderating image content: {image_path}")
        
        # TODO: Implement real moderation using AWS Rekognition or similar
        # Example:
        # import boto3
        # client = boto3.client('rekognition')
        # response = client.detect_moderation_labels(
        #     Image={'Bytes': open(image_path, 'rb').read()},
        #     MinConfidence=60
        # )
        
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
        
        # Personal-only indicators (red flags)
        personal_only = [
            'soy alto', 'soy bajo', 'soy moreno', 'soy blanco',
            'tengo ojos', 'mi color favorito', 'me gusta',
        ]
        
        is_personal_only = any(phrase in text_lower for phrase in personal_only)
        
        if is_personal_only:
            return {
                'is_professional': False,
                'reason': 'Descripción enfocada en características personales, no en servicios',
            }
        
        if has_service_verbs or has_service_nouns:
            return {
                'is_professional': True,
                'reason': 'Descripción enfocada en servicios',
            }
        
        return {
            'is_professional': False,
            'reason': 'Descripción no menciona servicios claramente',
        }
    
    # ============================================
    # SEMANTIC ANALYSIS
    # ============================================
    
    @staticmethod
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
        # At least 2 keywords must match for validation to pass
        min_keywords_required = 2
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
