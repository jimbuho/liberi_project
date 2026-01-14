# SCRIPT PARA VERIFICAR CONFIGURACIÓN DE PAYPHONE
# Ejecutar: python manage.py shell < check_payphone_config.py

from django.conf import settings
import requests

print("\n" + "="*60)
print("VERIFICACIÓN DE CONFIGURACIÓN PAYPHONE")
print("="*60 + "\n")

# 1. Verificar variables de entorno
print("1. Variables de Entorno:")
print("-" * 40)

payphone_token = getattr(settings, 'PAYPHONE_API_TOKEN', None)
payphone_store_id = getattr(settings, 'PAYPHONE_STORE_ID', None)
payphone_confirm_url = getattr(settings, 'PAYPHONE_URL_CONFIRM_PAYPHONE', None)

if payphone_token:
    print(f"✅ PAYPHONE_API_TOKEN: Configurado ({payphone_token[:10]}...)")
else:
    print("❌ PAYPHONE_API_TOKEN: NO CONFIGURADO")

if payphone_store_id:
    print(f"✅ PAYPHONE_STORE_ID: {payphone_store_id}")
else:
    print("❌ PAYPHONE_STORE_ID: NO CONFIGURADO")

if payphone_confirm_url:
    print(f"✅ PAYPHONE_URL_CONFIRM_PAYPHONE: {payphone_confirm_url}")
else:
    print("⚠️  PAYPHONE_URL_CONFIRM_PAYPHONE: NO CONFIGURADO (usará default)")
    print("   Default: https://pay.payphonetodoesposible.com/api/button/V2/Confirm")

print("\n2. Test de Conectividad:")
print("-" * 40)

# URL por defecto si no está configurada
test_url = payphone_confirm_url or 'https://pay.payphonetodoesposible.com/api/button/V2/Confirm'

try:
    # Intentar hacer un request de prueba (esperamos que falle con 401 o 400)
    response = requests.post(
        test_url,
        headers={
            'Authorization': f'Bearer {payphone_token}',
            'Content-Type': 'application/json'
        },
        json={
            'id': 12345,
            'clientTxId': 'test-123'
        },
        timeout=10
    )
    
    if response.status_code == 401:
        print("⚠️  Token inválido o expirado")
    elif response.status_code == 400:
        print("✅ Conexión OK - API respondiendo (error esperado por datos de prueba)")
    elif response.status_code == 404:
        print("❌ URL incorrecta - endpoint no encontrado")
    else:
        print(f"⚠️  Respuesta inesperada: {response.status_code}")
        print(f"   Body: {response.text[:200]}")
        
except requests.exceptions.Timeout:
    print("❌ TIMEOUT - No se puede conectar con PayPhone")
except requests.exceptions.ConnectionError as e:
    print(f"❌ ERROR DE CONEXIÓN: {e}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n3. Configuración del Callback:")
print("-" * 40)

base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
callback_url = f"{base_url}/payments/payphone/callback/"
print(f"URL de Callback: {callback_url}")
print("\n⚠️  IMPORTANTE: Esta URL debe estar configurada en PayPhone Developer")
print("   Ir a: https://developer.payphone.app/")
print("   Configurar el callback URL en tu aplicación")

print("\n4. Formato Esperado del Request:")
print("-" * 40)
print("""
PayPhone enviará los parámetros así:
GET /payments/payphone/callback/?id=69980637&clientTransactionId=8c193fd1-6936-426e-bfae-8d4f1f398fce

Tu sistema debe:
1. Capturar 'id' y 'clientTransactionId' de los parámetros GET
2. Hacer POST a la URL de confirmación con:
   {
     "id": 69980637,  // int
     "clientTxId": "8c193fd1-6936-426e-bfae-8d4f1f398fce"  // string
   }
3. Headers:
   - Authorization: Bearer {token}
   - Content-Type: application/json
""")

print("\n5. Checklist de Verificación:")
print("-" * 40)
print("□ Token configurado en .env")
print("□ Store ID configurado en .env")
print("□ Callback URL configurado en PayPhone Developer")
print("□ Callback URL usa HTTPS (no HTTP)")
print("□ Dominio accesible públicamente (no localhost)")
print("□ Celery corriendo para enviar emails")

print("\n" + "="*60)
print("FIN DE LA VERIFICACIÓN")
print("="*60 + "\n")