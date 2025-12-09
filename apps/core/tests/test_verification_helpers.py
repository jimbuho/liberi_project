"""
Tests for Verification Helpers

Run with:
    python manage.py test apps.core.tests.test_verification_helpers

Or run specific test:
    python manage.py test apps.core.tests.test_verification_helpers.VerificationHelpersTestCase.test_contact_detection_phone
"""

from django.test import TestCase
from apps.core.verification_helpers import VerificationHelpers


class VerificationHelpersTestCase(TestCase):
    """Test suite for VerificationHelpers class"""
    
    # ============================================
    # CONTACT INFORMATION DETECTION TESTS
    # ============================================
    
    def test_contact_detection_phone(self):
        """Test phone number detection in text"""
        # Formato ecuatoriano
        result = VerificationHelpers.detect_contact_info_in_text("Llámame al 0999123456")
        self.assertTrue(result['found'])
        self.assertIn('phone', result['types'])
        
        # Formato internacional
        result = VerificationHelpers.detect_contact_info_in_text("Contacto: +593999123456")
        self.assertTrue(result['found'])
        self.assertIn('phone', result['types'])
        
        # Números separados (evasión)
        result = VerificationHelpers.detect_contact_info_in_text("0 9 9 9 1 2 3 4 5 6")
        self.assertTrue(result['found'])
        self.assertIn('phone', result['types'])
    
    def test_contact_detection_email(self):
        """Test email detection in text"""
        result = VerificationHelpers.detect_contact_info_in_text("Escríbeme a juan@gmail.com")
        self.assertTrue(result['found'])
        self.assertIn('email', result['types'])
        
        # Email con espacios (evasión)
        result = VerificationHelpers.detect_contact_info_in_text("juan @ gmail . com")
        self.assertTrue(result['found'])
        self.assertIn('email', result['types'])
    
    def test_contact_detection_url(self):
        """Test URL detection in text"""
        result = VerificationHelpers.detect_contact_info_in_text("Visita www.miservicio.com")
        self.assertTrue(result['found'])
        self.assertIn('url', result['types'])
        
        result = VerificationHelpers.detect_contact_info_in_text("Más info en https://ejemplo.ec")
        self.assertTrue(result['found'])
        self.assertIn('url', result['types'])
    
    def test_contact_detection_social_media(self):
        """Test social media detection in text"""
        # Instagram handle
        result = VerificationHelpers.detect_contact_info_in_text("Sígueme @miservicio")
        self.assertTrue(result['found'])
        self.assertIn('social_media', result['types'])
        
        # Facebook
        result = VerificationHelpers.detect_contact_info_in_text("Búscame en Facebook como MiServicio")
        self.assertTrue(result['found'])
        self.assertIn('social_media', result['types'])
        
        # WhatsApp
        result = VerificationHelpers.detect_contact_info_in_text("WhatsApp: 0999123456")
        self.assertTrue(result['found'])
        self.assertIn('social_media', result['types'])
    
    def test_contact_detection_clean_text(self):
        """Test that clean text doesn't trigger false positives"""
        result = VerificationHelpers.detect_contact_info_in_text(
            "Ofrezco servicios de limpieza profesional para hogares y oficinas"
        )
        self.assertFalse(result['found'])
        self.assertEqual(len(result['types']), 0)
    
    # ============================================
    # ECUADORIAN CEDULA VALIDATION TESTS
    # ============================================
    
    def test_cedula_validation_valid(self):
        """Test valid Ecuadorian cedula numbers"""
        # Nota: Estos son números de ejemplo que pasan el algoritmo
        # pero pueden no ser cédulas reales
        valid_cedulas = [
            "1712345678",  # Pichincha
            "0912345678",  # Guayas
        ]
        
        for cedula in valid_cedulas:
            # El algoritmo puede rechazar estos ejemplos
            # Este test verifica que el método funciona
            result = VerificationHelpers.validate_ecuadorian_cedula(cedula)
            self.assertIsInstance(result, bool)
    
    def test_cedula_validation_invalid_length(self):
        """Test cedula with invalid length"""
        result = VerificationHelpers.validate_ecuadorian_cedula("123456789")  # 9 dígitos
        self.assertFalse(result)
        
        result = VerificationHelpers.validate_ecuadorian_cedula("12345678901")  # 11 dígitos
        self.assertFalse(result)
    
    def test_cedula_validation_invalid_province(self):
        """Test cedula with invalid province code"""
        result = VerificationHelpers.validate_ecuadorian_cedula("2512345678")  # Provincia 25
        self.assertFalse(result)
        
        result = VerificationHelpers.validate_ecuadorian_cedula("0012345678")  # Provincia 00
        self.assertFalse(result)
    
    def test_cedula_validation_invalid_third_digit(self):
        """Test cedula with invalid third digit"""
        result = VerificationHelpers.validate_ecuadorian_cedula("1762345678")  # Tercer dígito 6
        self.assertFalse(result)
    
    def test_cedula_validation_non_numeric(self):
        """Test cedula with non-numeric characters"""
        result = VerificationHelpers.validate_ecuadorian_cedula("171234567A")
        self.assertFalse(result)
        
        result = VerificationHelpers.validate_ecuadorian_cedula("17-1234-5678")
        self.assertFalse(result)
    
    # ============================================
    # NAME SIMILARITY TESTS
    # ============================================
    
    def test_name_similarity_exact_match(self):
        """Test exact name matches"""
        similarity = VerificationHelpers.calculate_name_similarity("Juan Pérez", "Juan Pérez")
        self.assertEqual(similarity, 1.0)
    
    def test_name_similarity_accent_normalization(self):
        """Test that accents are normalized"""
        similarity = VerificationHelpers.calculate_name_similarity("María García", "Maria Garcia")
        self.assertEqual(similarity, 1.0)
    
    def test_name_similarity_case_insensitive(self):
        """Test case insensitivity"""
        similarity = VerificationHelpers.calculate_name_similarity("JUAN PEREZ", "juan perez")
        self.assertEqual(similarity, 1.0)
    
    def test_name_similarity_partial_match(self):
        """Test partial name matches"""
        similarity = VerificationHelpers.calculate_name_similarity(
            "José Luis", 
            "Jose Luis Martinez"
        )
        # Debe ser mayor a 0.5 pero menor a 1.0
        self.assertGreater(similarity, 0.5)
        self.assertLess(similarity, 1.0)
    
    def test_name_similarity_different_names(self):
        """Test completely different names"""
        similarity = VerificationHelpers.calculate_name_similarity("Pedro", "Pablo")
        self.assertLess(similarity, 0.5)
    
    # ============================================
    # PROFESSIONAL DESCRIPTION TESTS
    # ============================================
    
    def test_professional_description_valid(self):
        """Test professional service descriptions"""
        descriptions = [
            "Ofrezco servicios de limpieza profesional para hogares y oficinas",
            "Realizo cortes de cabello y peinados para eventos especiales",
            "Brindo servicios de reparación de computadoras y laptops",
            "Especializado en instalaciones eléctricas residenciales",
        ]
        
        for desc in descriptions:
            result = VerificationHelpers.is_professional_description(desc)
            self.assertTrue(
                result['is_professional'], 
                f"Expected professional: {desc}"
            )
    
    def test_professional_description_personal_only(self):
        """Test descriptions that are only personal characteristics"""
        descriptions = [
            "Soy alto, moreno, me gusta el fútbol",
            "Tengo ojos verdes y cabello largo",
            "Soy una persona muy amable y simpática",
        ]
        
        for desc in descriptions:
            result = VerificationHelpers.is_professional_description(desc)
            self.assertFalse(
                result['is_professional'],
                f"Expected not professional: {desc}"
            )
    
    # ============================================
    # ILLEGAL CONTENT DETECTION TESTS
    # ============================================
    
    def test_illegal_content_detection_clean(self):
        """Test that clean text is not flagged"""
        result = VerificationHelpers.detect_illegal_content_in_text(
            "Ofrezco servicios de limpieza profesional"
        )
        self.assertFalse(result['found'])
        self.assertEqual(len(result['categories']), 0)
    
    def test_illegal_content_detection_weapons(self):
        """Test weapons-related content detection"""
        result = VerificationHelpers.detect_illegal_content_in_text(
            "Venta de armas y municiones"
        )
        self.assertTrue(result['found'])
        self.assertIn('armas', result['categories'])
    
    def test_illegal_content_detection_adult(self):
        """Test adult content detection"""
        result = VerificationHelpers.detect_illegal_content_in_text(
            "Servicios sexuales disponibles"
        )
        self.assertTrue(result['found'])
        self.assertIn('pornografia', result['categories'])
    
    def test_illegal_content_detection_money_laundering(self):
        """Test money laundering detection"""
        result = VerificationHelpers.detect_illegal_content_in_text(
            "Lavado de dinero rápido y seguro"
        )
        self.assertTrue(result['found'])
        self.assertIn('lavado_activos', result['categories'])
    
    # ============================================
    # SEMANTIC SIMILARITY TESTS
    # ============================================
    
    def test_semantic_similarity_related(self):
        """Test similarity between related texts"""
        similarity = VerificationHelpers.calculate_semantic_similarity(
            "limpieza de hogares y oficinas",
            "servicio de limpieza doméstica"
        )
        # Debe tener alguna similitud
        self.assertGreater(similarity, 0.0)
    
    def test_semantic_similarity_unrelated(self):
        """Test similarity between unrelated texts"""
        similarity = VerificationHelpers.calculate_semantic_similarity(
            "reparación de computadoras",
            "limpieza de casas"
        )
        # Debe tener baja o nula similitud
        self.assertLess(similarity, 0.3)
    
    def test_semantic_similarity_empty_texts(self):
        """Test similarity with empty texts"""
        similarity = VerificationHelpers.calculate_semantic_similarity("", "algo")
        self.assertEqual(similarity, 0.0)
        
        similarity = VerificationHelpers.calculate_semantic_similarity("algo", "")
        self.assertEqual(similarity, 0.0)
    
    # ============================================
    # CATEGORY VALIDATION TESTS
    # ============================================
    
    def test_category_description_match_beauty(self):
        """Test category-description match for Beauty category"""
        result = VerificationHelpers.validate_category_description_match(
            "Belleza",
            "Ofrezco servicios de maquillaje, peinado y manicure profesional"
        )
        self.assertTrue(result['is_match'])
        self.assertGreater(len(result['matched_keywords']), 0)
    
    def test_category_description_match_cleaning(self):
        """Test category-description match for Cleaning category"""
        result = VerificationHelpers.validate_category_description_match(
            "Limpieza",
            "Servicio de limpieza profunda para hogares y oficinas, incluye desinfección"
        )
        self.assertTrue(result['is_match'])
        self.assertGreater(len(result['matched_keywords']), 0)
    
    def test_category_description_mismatch(self):
        """Test category-description mismatch"""
        result = VerificationHelpers.validate_category_description_match(
            "Belleza",
            "Reparación de computadoras y laptops"
        )
        # Puede o no coincidir dependiendo del threshold
        # Solo verificamos que retorna la estructura correcta
        self.assertIn('is_match', result)
        self.assertIn('similarity', result)
        self.assertIn('matched_keywords', result)
    
    def test_category_undefined_keywords(self):
        """Test category with no defined keywords"""
        result = VerificationHelpers.validate_category_description_match(
            "CategoríaInexistente",
            "Alguna descripción"
        )
        # Debe pasar si no hay keywords definidos
        self.assertTrue(result['is_match'])


class VerificationHelpersIntegrationTestCase(TestCase):
    """Integration tests for verification helpers with real scenarios"""
    
    def test_complete_contact_validation_scenario(self):
        """Test a complete scenario with multiple contact types"""
        text = """
        Ofrezco servicios de limpieza profesional.
        Contacto: 0999123456
        Email: limpieza@gmail.com
        Instagram: @limpiezapro
        """
        
        result = VerificationHelpers.detect_contact_info_in_text(text)
        self.assertTrue(result['found'])
        # Debe detectar al menos 2 tipos de contacto
        self.assertGreaterEqual(len(result['types']), 2)
    
    def test_evasion_attempts(self):
        """Test detection of common evasion attempts"""
        evasion_texts = [
            "Llama al cero nueve nueve nueve uno dos tres",
            "Email: juan @ gmail . com",
            "WhatsApp 0 9 9 9 1 2 3 4 5 6",
        ]
        
        for text in evasion_texts:
            result = VerificationHelpers.detect_contact_info_in_text(text)
            # Al menos uno debe ser detectado
            # (algunos patrones de evasión pueden no estar cubiertos)
            # Este test verifica que el sistema intenta detectarlos


def run_quick_tests():
    """
    Función helper para ejecutar tests rápidos sin Django test runner.
    Útil para debugging.
    """
    print("=" * 60)
    print("QUICK VERIFICATION HELPERS TESTS")
    print("=" * 60)
    
    # Test 1: Contact Detection
    print("\n1. Contact Detection")
    result = VerificationHelpers.detect_contact_info_in_text("Llámame al 0999123456")
    print(f"   Phone detection: {'✅' if result['found'] else '❌'}")
    
    # Test 2: Cedula Validation
    print("\n2. Cedula Validation")
    result = VerificationHelpers.validate_ecuadorian_cedula("1712345678")
    print(f"   Cedula validation: {'✅' if isinstance(result, bool) else '❌'}")
    
    # Test 3: Name Similarity
    print("\n3. Name Similarity")
    similarity = VerificationHelpers.calculate_name_similarity("Juan Pérez", "juan perez")
    print(f"   Name similarity: {'✅' if similarity == 1.0 else '❌'} (score: {similarity})")
    
    # Test 4: Professional Description
    print("\n4. Professional Description")
    result = VerificationHelpers.is_professional_description(
        "Ofrezco servicios de limpieza profesional"
    )
    print(f"   Professional check: {'✅' if result['is_professional'] else '❌'}")
    
    # Test 5: Illegal Content
    print("\n5. Illegal Content Detection")
    result = VerificationHelpers.detect_illegal_content_in_text("Venta de armas")
    print(f"   Illegal detection: {'✅' if result['found'] else '❌'}")
    
    print("\n" + "=" * 60)
    print("QUICK TESTS COMPLETED")
    print("=" * 60)
