"""
Quick test script for verification helpers.
Run with: python apps/core/test_verification_quick.py
"""

from apps.core.verification_helpers import VerificationHelpers

print("=" * 60)
print("TESTING VERIFICATION HELPERS")
print("=" * 60)

# Test 1: Contact Info Detection in Text
print("\n1. Testing Contact Info Detection in Text")
print("-" * 60)

test_texts = [
    ("Llámame al 0999123456", True, "phone"),
    ("Mi email es juan@gmail.com", True, "email"),
    ("Visita www.miservicio.com", True, "url"),
    ("Sígueme en Instagram @miservicio", True, "social_media"),
    ("Ofrezco servicios de limpieza profesional", False, None),
]

for text, should_find, expected_type in test_texts:
    result = VerificationHelpers.detect_contact_info_in_text(text)
    status = "✅" if result['found'] == should_find else "❌"
    print(f"{status} '{text[:40]}...' -> Found: {result['found']}, Types: {result['types']}")

# Test 2: Ecuadorian Cedula Validation
print("\n2. Testing Ecuadorian Cedula Validation")
print("-" * 60)

test_cedulas = [
    ("1234567890", False),  # Invalid
    ("0123456789", False),  # Invalid province
    ("1712345678", True),   # Valid format (Pichincha)
]

for cedula, should_be_valid in test_cedulas:
    result = VerificationHelpers.validate_ecuadorian_cedula(cedula)
    status = "✅" if result == should_be_valid else "❌"
    print(f"{status} Cédula {cedula}: Valid = {result} (expected {should_be_valid})")

# Test 3: Name Similarity
print("\n3. Testing Name Similarity")
print("-" * 60)

name_pairs = [
    ("Juan Pérez", "juan perez", 1.0),
    ("María García", "Maria Garcia", 1.0),  # Without accents
    ("José Luis", "Jose Luis Martinez", 0.7),  # Partial match
    ("Pedro", "Pablo", 0.3),  # Different
]

for name1, name2, expected_min in name_pairs:
    similarity = VerificationHelpers.calculate_name_similarity(name1, name2)
    status = "✅" if similarity >= expected_min else "❌"
    print(f"{status} '{name1}' vs '{name2}': {similarity:.2f} (expected >= {expected_min})")

# Test 4: Professional Description Analysis
print("\n4. Testing Professional Description Analysis")
print("-" * 60)

descriptions = [
    ("Ofrezco servicios de limpieza profesional para hogares y oficinas", True),
    ("Realizo cortes de cabello y peinados para eventos", True),
    ("Soy alto, moreno, me gusta el fútbol", False),
    ("Tengo ojos verdes y cabello largo", False),
]

for desc, should_be_professional in descriptions:
    result = VerificationHelpers.is_professional_description(desc)
    status = "✅" if result['is_professional'] == should_be_professional else "❌"
    print(f"{status} Professional: {result['is_professional']} - {desc[:50]}...")

# Test 5: Illegal Content Detection
print("\n5. Testing Illegal Content Detection")
print("-" * 60)

test_illegal = [
    ("Ofrezco servicios de limpieza", False),
    ("Venta de armas y municiones", True),
    ("Servicios sexuales disponibles", True),
    ("Lavado de dinero rápido", True),
]

for text, should_find_illegal in test_illegal:
    result = VerificationHelpers.detect_illegal_content_in_text(text)
    status = "✅" if result['found'] == should_find_illegal else "❌"
    categories = result['categories'] if result['found'] else []
    print(f"{status} '{text}' -> Illegal: {result['found']}, Categories: {categories}")

# Test 6: Semantic Similarity
print("\n6. Testing Semantic Similarity")
print("-" * 60)

text_pairs = [
    ("limpieza de hogares", "servicio de limpieza doméstica", 0.3),
    ("corte de cabello", "peluquería y estilismo", 0.2),
    ("reparación de computadoras", "limpieza de casas", 0.0),
]

for text1, text2, expected_min in text_pairs:
    similarity = VerificationHelpers.calculate_semantic_similarity(text1, text2)
    status = "✅" if similarity >= expected_min else "⚠️"
    print(f"{status} '{text1}' vs '{text2}': {similarity:.2f} (expected >= {expected_min})")

print("\n" + "=" * 60)
print("TESTS COMPLETED")
print("=" * 60)
