"""
Script para listar TODOS los templates en Twilio y su estado de aprobación.
Esto te ayudará a identificar cuáles puedes usar ahora.
"""
import os
import django
from twilio.rest import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*80)
print("🔍 LISTANDO TODOS LOS TEMPLATES EN TWILIO")
print("="*80)

ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
client = Client(ACCOUNT_SID, AUTH_TOKEN)

print("\n📋 Obteniendo todos los Content Templates...")
print("-"*80)

try:
    # Obtener todos los templates
    contents = client.content.v1.contents.list(limit=100)
    
    if not contents:
        print("   ⚠️  No se encontraron templates")
    else:
        print(f"\n   ✅ Total de templates encontrados: {len(contents)}")
        
        approved_templates = []
        rejected_templates = []
        pending_templates = []
        other_templates = []
        
        print("\n" + "="*80)
        print("📊 DETALLES DE CADA TEMPLATE")
        print("="*80)
        
        for i, content in enumerate(contents, 1):
            print(f"\n{i}. {content.friendly_name}")
            print(f"   SID: {content.sid}")
            print(f"   Idioma: {content.language}")
            
            # Intentar determinar el estado
            # Nota: La API puede no exponer approval_status directamente
            # pero podemos inferirlo de otros campos
            
            types_str = str(content.types)
            
            # Verificar si tiene contenido válido
            if content.types and len(content.types) > 0:
                status_icon = "✅"
                status = "APPROVED (probablemente)"
                approved_templates.append(content)
            else:
                status_icon = "❓"
                status = "UNKNOWN"
                other_templates.append(content)
            
            print(f"   {status_icon} Estado: {status}")
            print(f"   Tipos: {list(content.types.keys()) if content.types else 'N/A'}")
            
            # Mostrar si coincide con los configurados
            configured_match = None
            for template_name, template_info in settings.TWILIO_TEMPLATES.items():
                if template_info['content_sid'] == content.sid:
                    configured_match = template_name
                    break
            
            if configured_match:
                print(f"   🔗 Configurado como: {configured_match}")
            else:
                print(f"   ⚠️  NO está configurado en settings.py")
        
        # Resumen
        print("\n" + "="*80)
        print("📊 RESUMEN")
        print("="*80)
        
        print(f"\n   Total: {len(contents)} templates")
        print(f"   ✅ Probablemente aprobados: {len(approved_templates)}")
        print(f"   ❓ Estado desconocido: {len(other_templates)}")
        
        # Recomendaciones
        print("\n" + "="*80)
        print("💡 RECOMENDACIONES")
        print("="*80)
        
        print("\n1. Ve a la consola de Twilio para ver el estado exacto:")
        print("   🔗 https://console.twilio.com/us1/develop/sms/content-template-builder")
        
        print("\n2. Busca templates con estado:")
        print("   ✅ Approved (verde) - Puedes usarlos")
        print("   ⏳ Pending (amarillo) - Esperando aprobación de Meta")
        print("   ❌ Rejected (rojo) - Necesitas duplicar y reenviar")
        
        print("\n3. Para templates rechazados:")
        print("   a) Abre el template")
        print("   b) Click en 'Duplicate'")
        print("   c) Reenvía para aprobación")
        print("   d) Actualiza el Content SID en tu .env")
        
        print("\n4. Templates configurados actualmente en settings.py:")
        print("-"*80)
        for template_name, template_info in settings.TWILIO_TEMPLATES.items():
            print(f"\n   {template_name}:")
            print(f"      SID: {template_info['content_sid']}")
            
            # Verificar si existe
            found = False
            for content in contents:
                if content.sid == template_info['content_sid']:
                    found = True
                    print(f"      ✅ Encontrado: {content.friendly_name}")
                    break
            
            if not found:
                print(f"      ❌ NO ENCONTRADO - Puede estar eliminado o el SID es incorrecto")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ Análisis completado")
print("="*80)

print("\n🎯 PRÓXIMO PASO:")
print("   Ve a: https://console.twilio.com/us1/develop/sms/content-template-builder")
print("   Y verifica visualmente el estado de cada template")
print()
