#!/usr/bin/env python
"""
Script para verificar el estado de las dependencias de verificación.
Uso: python check_verification_deps.py
"""

import sys

print("=" * 60)
print("VERIFICACIÓN DE DEPENDENCIAS - SISTEMA DE VALIDACIÓN")
print("=" * 60)
print()

# Check 1: PIL/Pillow
print("1. Procesamiento de Imágenes (PIL/Pillow)")
try:
    from PIL import Image
    import PIL
    print(f"   ✅ PIL/Pillow {PIL.__version__} - INSTALADO")
except ImportError:
    print("   ❌ PIL/Pillow - NO INSTALADO")
    print("      Instalar con: pip install Pillow")

# Check 2: numpy
print("\n2. NumPy (para procesamiento de imágenes)")
try:
    import numpy as np
    print(f"   ✅ NumPy {np.__version__} - INSTALADO")
except ImportError:
    print("   ❌ NumPy - NO INSTALADO")
    print("      Instalar con: pip install numpy")

# Check 3: pytesseract
print("\n3. OCR - pytesseract")
try:
    import pytesseract
    print(f"   ✅ pytesseract - INSTALADO")
    
    # Try to get Tesseract version
    try:
        version = pytesseract.get_tesseract_version()
        print(f"   ✅ Tesseract {version} - INSTALADO EN EL SISTEMA")
    except Exception as e:
        print(f"   ⚠️  pytesseract instalado pero Tesseract no encontrado en el sistema")
        print(f"      Error: {e}")
        print("      Instalar Tesseract:")
        print("        macOS: brew install tesseract tesseract-lang")
        print("        Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-spa")
        
except ImportError:
    print("   ❌ pytesseract - NO INSTALADO (usando modo mock)")
    print("      Instalar con: pip install pytesseract")

# Check 4: face_recognition
print("\n4. Reconocimiento Facial - face_recognition")
try:
    import face_recognition
    print(f"   ✅ face_recognition - INSTALADO")
    
    # Check dlib
    try:
        import dlib
        print(f"   ✅ dlib {dlib.__version__} - INSTALADO")
    except ImportError:
        print("   ⚠️  dlib - NO INSTALADO (requerido por face_recognition)")
        
except ImportError:
    print("   ❌ face_recognition - NO INSTALADO (usando modo mock)")
    print("      Instalar con: pip install face-recognition")

# Check 5: Django
print("\n5. Django")
try:
    import django
    print(f"   ✅ Django {django.__version__} - INSTALADO")
except ImportError:
    print("   ❌ Django - NO INSTALADO")
    print("      Instalar con: pip install django")

print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)

# Summary
try:
    import pytesseract
    import face_recognition
    print("✅ CONFIGURACIÓN COMPLETA")
    print("   Todas las funcionalidades de verificación están disponibles.")
except ImportError:
    try:
        import pytesseract
        print("⚠️  CONFIGURACIÓN PARCIAL")
        print("   OCR disponible, reconocimiento facial en modo mock.")
    except ImportError:
        print("ℹ️  MODO BÁSICO")
        print("   Sistema funcionando en modo mock (sin OCR ni facial recognition).")
        print("   El sistema funciona correctamente, pero sin validación real de imágenes.")

print("\n📖 Para más información, consulta: OCR_INSTALLATION_GUIDE.md")
print("=" * 60)
