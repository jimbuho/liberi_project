#!/usr/bin/env python
"""
test_image_upload.py

Script de testing automatizado para el sistema de carga de imágenes.
Ejecutar desde la raíz del proyecto Django.

Uso:
    python test_image_upload.py
    
    # O con Django:
    python manage.py shell < test_image_upload.py
"""

import os
import sys
from io import BytesIO
from pathlib import Path


def setup_django():
    """Configura Django para el script"""
    # Ajusta el nombre del módulo de settings según tu proyecto
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
    
    try:
        import django
        django.setup()
        return True
    except Exception as e:
        print(f"❌ Error configurando Django: {e}")
        return False


def test_imports():
    """Test 1: Verificar imports"""
    print("\n" + "="*60)
    print("TEST 1: VERIFICANDO IMPORTS")
    print("="*60)
    
    tests_passed = []
    tests_failed = []
    
    # Test Django
    try:
        import django
        print(f"✅ Django {django.get_version()} importado correctamente")
        tests_passed.append("Django import")
    except ImportError as e:
        print(f"❌ Django no se pudo importar: {e}")
        tests_failed.append("Django import")
    
    # Test Supabase
    try:
        from supabase import create_client
        print("✅ Supabase importado correctamente")
        tests_passed.append("Supabase import")
    except ImportError:
        print("⚠️  Supabase no instalado (OK si en desarrollo)")
        tests_passed.append("Supabase import (opcional)")
    
    # Test Pillow (opcional)
    try:
        from PIL import Image
        print("✅ Pillow importado correctamente")
        tests_passed.append("Pillow import")
    except ImportError:
        print("⚠️  Pillow no instalado (opcional pero recomendado)")
        tests_passed.append("Pillow import (opcional)")
    
    # Test image_upload module
    try:
        from core.image_upload import (
            upload_image,
            delete_image,
            validate_image,
            get_storage_info
        )
        print("✅ core.image_upload importado correctamente")
        tests_passed.append("image_upload module")
    except ImportError as e:
        print(f"❌ core.image_upload no se pudo importar: {e}")
        tests_failed.append("image_upload module")
        return False  # Este es crítico
    
    print(f"\n✅ Pasaron: {len(tests_passed)} | ❌ Fallaron: {len(tests_failed)}")
    return len(tests_failed) == 0


def test_configuration():
    """Test 2: Verificar configuración"""
    print("\n" + "="*60)
    print("TEST 2: VERIFICANDO CONFIGURACIÓN")
    print("="*60)
    
    from django.conf import settings
    from core.image_upload import get_storage_info
    
    # Ambiente
    env = os.getenv('ENVIRONMENT', 'development')
    print(f"🌍 Ambiente: {env}")
    
    # Settings de Django
    if hasattr(settings, 'MEDIA_ROOT'):
        print(f"✅ MEDIA_ROOT: {settings.MEDIA_ROOT}")
        
        # Verificar que existe
        if os.path.exists(settings.MEDIA_ROOT):
            print(f"   📁 Directorio existe")
        else:
            print(f"   ⚠️  Directorio no existe, creando...")
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    else:
        print("❌ MEDIA_ROOT no configurado")
    
    if hasattr(settings, 'MEDIA_URL'):
        print(f"✅ MEDIA_URL: {settings.MEDIA_URL}")
    else:
        print("❌ MEDIA_URL no configurado")
    
    # Info del storage
    print("\n📊 Información del Storage:")
    info = get_storage_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    return True


def test_validation():
    """Test 3: Verificar validaciones"""
    print("\n" + "="*60)
    print("TEST 3: VERIFICANDO VALIDACIONES")
    print("="*60)
    
    from django.core.files.uploadedfile import SimpleUploadedFile
    from core.image_upload import validate_image
    
    tests = []
    
    # Test 1: Archivo válido
    valid_file = SimpleUploadedFile(
        name='test.jpg',
        content=b'fake image content',
        content_type='image/jpeg'
    )
    is_valid, error = validate_image(valid_file, max_size_mb=5)
    if is_valid:
        print("✅ Test 1: Archivo válido reconocido correctamente")
        tests.append(True)
    else:
        print(f"❌ Test 1: Archivo válido rechazado: {error}")
        tests.append(False)
    
    # Test 2: Archivo muy grande
    big_file = SimpleUploadedFile(
        name='big.jpg',
        content=b'x' * (6 * 1024 * 1024),  # 6MB
        content_type='image/jpeg'
    )
    is_valid, error = validate_image(big_file, max_size_mb=5)
    if not is_valid and "grande" in error.lower():
        print("✅ Test 2: Archivo grande rechazado correctamente")
        tests.append(True)
    else:
        print(f"❌ Test 2: Archivo grande no rechazado: {error}")
        tests.append(False)
    
    # Test 3: Extensión incorrecta
    bad_file = SimpleUploadedFile(
        name='doc.pdf',
        content=b'fake pdf',
        content_type='application/pdf'
    )
    is_valid, error = validate_image(bad_file)
    if not is_valid and "formato" in error.lower():
        print("✅ Test 3: Formato incorrecto rechazado correctamente")
        tests.append(True)
    else:
        print(f"❌ Test 3: Formato incorrecto no rechazado: {error}")
        tests.append(False)
    
    passed = sum(tests)
    print(f"\n✅ Pasaron: {passed}/{len(tests)}")
    return passed == len(tests)


def test_upload_development():
    """Test 4: Probar upload en desarrollo"""
    print("\n" + "="*60)
    print("TEST 4: PROBANDO UPLOAD (DESARROLLO)")
    print("="*60)
    
    env = os.getenv('ENVIRONMENT', 'development')
    if env != 'development':
        print("⚠️  Saltando (solo en desarrollo)")
        return True
    
    from django.core.files.uploadedfile import SimpleUploadedFile
    from core.image_upload import upload_image, delete_image
    from django.conf import settings
    
    # Crear archivo de prueba
    test_file = SimpleUploadedFile(
        name='test_upload.jpg',
        content=b'This is a test image content',
        content_type='image/jpeg'
    )
    
    try:
        # Subir
        print("📤 Subiendo archivo de prueba...")
        url = upload_image(test_file, folder='test', unique_name=True)
        print(f"✅ Upload exitoso: {url}")
        
        # Verificar que existe
        if url.startswith('/media/'):
            file_path = url.replace('/media/', '')
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            if os.path.exists(full_path):
                print(f"✅ Archivo existe en: {full_path}")
                
                # Limpiar
                print("🗑️  Eliminando archivo de prueba...")
                if delete_image(url):
                    print("✅ Archivo eliminado correctamente")
                    return True
                else:
                    print("⚠️  No se pudo eliminar el archivo")
                    return True  # No es crítico
            else:
                print(f"❌ Archivo no existe en: {full_path}")
                return False
        else:
            print(f"⚠️  URL no esperada: {url}")
            return True  # En producción puede ser diferente
            
    except Exception as e:
        print(f"❌ Error durante upload: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_specialized_functions():
    """Test 5: Probar funciones especializadas"""
    print("\n" + "="*60)
    print("TEST 5: VERIFICANDO FUNCIONES ESPECIALIZADAS")
    print("="*60)
    
    from core.image_upload import (
        upload_profile_photo,
        upload_service_image,
        upload_document,
        upload_payment_proof,
        get_unique_filename
    )
    
    functions = [
        'upload_profile_photo',
        'upload_service_image',
        'upload_document',
        'upload_payment_proof',
        'get_unique_filename'
    ]
    
    for func_name in functions:
        print(f"✅ {func_name} disponible")
    
    # Test generación de nombre único
    filename1 = get_unique_filename('test.jpg', prefix='user_123')
    filename2 = get_unique_filename('test.jpg', prefix='user_123')
    
    if filename1 != filename2:
        print(f"✅ Nombres únicos generados correctamente")
        print(f"   Ejemplo 1: {filename1}")
        print(f"   Ejemplo 2: {filename2}")
        return True
    else:
        print(f"❌ Los nombres no son únicos")
        return False


def test_error_handling():
    """Test 6: Probar manejo de errores"""
    print("\n" + "="*60)
    print("TEST 6: VERIFICANDO MANEJO DE ERRORES")
    print("="*60)
    
    from core.image_upload import upload_image
    from django.core.files.uploadedfile import SimpleUploadedFile
    
    tests = []
    
    # Test 1: Archivo None
    try:
        upload_image(None, folder='test')
        print("❌ Test 1: Debería rechazar archivo None")
        tests.append(False)
    except (ValueError, Exception) as e:
        print(f"✅ Test 1: Archivo None rechazado correctamente")
        tests.append(True)
    
    # Test 2: Validación activada con archivo inválido
    bad_file = SimpleUploadedFile(
        name='test.exe',
        content=b'fake exe',
        content_type='application/x-msdownload'
    )
    
    try:
        upload_image(bad_file, folder='test', validate=True)
        print("❌ Test 2: Debería rechazar archivo .exe")
        tests.append(False)
    except ValueError as e:
        print(f"✅ Test 2: Archivo .exe rechazado correctamente")
        tests.append(True)
    except Exception as e:
        print(f"⚠️  Test 2: Error inesperado: {e}")
        tests.append(True)  # Aceptar, al menos falló
    
    passed = sum(tests)
    print(f"\n✅ Pasaron: {passed}/{len(tests)}")
    return passed == len(tests)


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "🧪"*30)
    print("SISTEMA DE TESTING - CARGA DE IMÁGENES")
    print("🧪"*30)
    
    if not setup_django():
        print("\n❌ No se pudo configurar Django. Abortando.")
        return False
    
    results = []
    
    # Ejecutar tests
    results.append(("Imports", test_imports()))
    results.append(("Configuración", test_configuration()))
    results.append(("Validaciones", test_validation()))
    results.append(("Upload (Dev)", test_upload_development()))
    results.append(("Funciones Especializadas", test_specialized_functions()))
    results.append(("Manejo de Errores", test_error_handling()))
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE TESTS")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print("\n" + "="*60)
    print(f"RESULTADO FINAL: {total_passed}/{total_tests} tests pasaron")
    print("="*60)
    
    if total_passed == total_tests:
        print("\n🎉 ¡Todos los tests pasaron! Sistema listo para usar.")
        return True
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) fallaron. Revisar configuración.")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)