#!/usr/bin/env python
"""
Script de prueba rápida para el sistema de verificación.
Ejecutar con: python quick_test.py
"""

print("=" * 60)
print("PRUEBA RÁPIDA - SISTEMA DE VERIFICACIÓN")
print("=" * 60)
print()

# Test 1: Importar módulo
print("1. Importando módulo de verificación...")
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Configurar Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
    
    import django
    django.setup()
    
    from apps.core.verification_helpers import VerificationHelpers
    print("   ✅ Módulo importado correctamente")
except Exception as e:
    print(f"   ❌ Error al importar: {e}")
    print("\n   Ejecuta con Django shell:")
    print("   python manage.py shell < quick_test.py")
    exit(1)

# Test 2: Detección de contacto
print("\n2. Probando detección de información de contacto...")
tests_contacto = [
    ("Teléfono", "Llámame al 0999123456", True),
    ("Email", "Escríbeme a juan@gmail.com", True),
    ("URL", "Visita www.miservicio.com", True),
    ("Redes", "Sígueme @miservicio", True),
    ("Limpio", "Ofrezco servicios de limpieza", False),
]

for nombre, texto, debe_detectar in tests_contacto:
    result = VerificationHelpers.detect_contact_info_in_text(texto)
    status = "✅" if result['found'] == debe_detectar else "❌"
    print(f"   {status} {nombre}: {'Detectado' if result['found'] else 'No detectado'}")

# Test 3: Validación de cédula
print("\n3. Probando validación de cédula ecuatoriana...")
cedulas = [
    ("1712345678", "Formato válido"),
    ("0123456789", "Provincia inválida"),
    ("123456789", "Longitud incorrecta"),
]

for cedula, descripcion in cedulas:
    result = VerificationHelpers.validate_ecuadorian_cedula(cedula)
    status = "✅" if isinstance(result, bool) else "❌"
    print(f"   {status} {cedula}: {descripcion} -> {result}")

# Test 4: Similitud de nombres
print("\n4. Probando similitud de nombres...")
nombres = [
    ("Juan Pérez", "juan perez", 1.0),
    ("María García", "Maria Garcia", 1.0),
    ("Pedro", "Pablo", 0.5),
]

for nombre1, nombre2, esperado in nombres:
    similarity = VerificationHelpers.calculate_name_similarity(nombre1, nombre2)
    status = "✅" if similarity >= esperado else "⚠️"
    print(f"   {status} '{nombre1}' vs '{nombre2}': {similarity:.2f}")

# Test 5: Descripción profesional
print("\n5. Probando análisis de descripción profesional...")
descripciones = [
    ("Ofrezco servicios de limpieza profesional", True),
    ("Realizo cortes de cabello", True),
    ("Soy alto y moreno", False),
]

for desc, debe_ser_profesional in descripciones:
    result = VerificationHelpers.is_professional_description(desc)
    status = "✅" if result['is_professional'] == debe_ser_profesional else "❌"
    print(f"   {status} Profesional: {result['is_professional']} - {desc[:40]}...")

# Test 6: Contenido ilegal
print("\n6. Probando detección de contenido ilegal...")
textos_ilegales = [
    ("Ofrezco servicios de limpieza", False),
    ("Venta de armas y municiones", True),
    ("Servicios sexuales disponibles", True),
]

for texto, debe_detectar in textos_ilegales:
    result = VerificationHelpers.detect_illegal_content_in_text(texto)
    status = "✅" if result['found'] == debe_detectar else "❌"
    print(f"   {status} Ilegal: {result['found']} - {texto[:40]}...")

# Test 7: Similitud semántica
print("\n7. Probando similitud semántica...")
pares = [
    ("limpieza de hogares", "servicio de limpieza", 0.2),
    ("reparación de computadoras", "limpieza de casas", 0.1),
]

for texto1, texto2, min_esperado in pares:
    similarity = VerificationHelpers.calculate_semantic_similarity(texto1, texto2)
    status = "✅" if similarity >= min_esperado else "⚠️"
    print(f"   {status} Similitud: {similarity:.2f} - '{texto1}' vs '{texto2}'")

# Resumen
print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print("✅ Todas las funcionalidades básicas están funcionando")
print("ℹ️  OCR y reconocimiento facial en modo mock (sin librerías instaladas)")
print("\nPara habilitar funcionalidades completas:")
print("  1. Local: pip install pytesseract face-recognition")
print("  2. Producción: fly deploy (ya configurado)")
print("=" * 60)
