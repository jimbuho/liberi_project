import os
import django
import json
from twilio.rest import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()
from django.conf import settings

print("="*70)
print("🔍 VERIFICACIÓN DETALLADA DE TEMPLATES")
print("="*70)

ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
client = Client(ACCOUNT_SID, AUTH_TOKEN)

TEMPLATES = settings.TWILIO_TEMPLATES

for template_name, template_info in TEMPLATES.items():
    content_sid = template_info['content_sid']
    
    print(f"\n{'='*70}")
    print(f"📋 Template: {template_name}")
    print(f"{'='*70}")
    print(f"🆔 Content SID: {content_sid}")
    
    try:
        content = client.content.v1.contents(content_sid).fetch()
        
        print(f"✅ Nombre: {content.friendly_name}")
        print(f"✅ Idioma: {content.language}")
        
        # Obtener los tipos de contenido
        types = content.types
        print(f"\n📝 Tipos de contenido:")
        
        for content_type, content_data in types.items():
            print(f"\n   Tipo: {content_type}")
            print(f"   Datos: {json.dumps(content_data, indent=6, ensure_ascii=False)}")
            
            # Contar variables en el template
            body = content_data.get('body', '')
            variables = []
            i = 1
            while f'{{{{{i}}}}}' in body:
                variables.append(f'{{{{{i}}}}}')
                i += 1
            
            print(f"\n   📊 Variables encontradas en el body: {len(variables)}")
            if variables:
                print(f"   Variables: {', '.join(variables)}")
            
            # Verificar acciones (botones)
            if 'actions' in content_data:
                actions = content_data['actions']
                print(f"\n   🔘 Acciones (botones): {len(actions)}")
                for idx, action in enumerate(actions, 1):
                    print(f"      {idx}. {action.get('title', 'N/A')} - {action.get('url', 'N/A')}")
                    # Contar variables en URLs
                    url = action.get('url', '')
                    url_vars = []
                    j = 1
                    while f'{{{{{j}}}}}' in url:
                        url_vars.append(f'{{{{{j}}}}}')
                        j += 1
                    if url_vars:
                        print(f"         Variables en URL: {', '.join(url_vars)}")
        
        # Calcular total de variables únicas
        all_text = json.dumps(types)
        total_vars = set()
        i = 1
        while f'{{{{{i}}}}}' in all_text:
            total_vars.add(i)
            i += 1
        
        print(f"\n   ✅ Total de variables únicas: {len(total_vars)}")
        print(f"   Variables: {sorted(total_vars)}")
        
        expected_vars = template_info['variables_count']
        if len(total_vars) != expected_vars:
            print(f"\n   ⚠️  ADVERTENCIA:")
            print(f"      Configurado en settings.py: {expected_vars} variables")
            print(f"      Encontrado en template: {len(total_vars)} variables")
            print(f"      ❌ NO COINCIDEN - Actualiza settings.py")
        else:
            print(f"\n   ✅ Coincide con settings.py: {expected_vars} variables")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*70)
print("📊 RESUMEN")
print("="*70)

print("\n💡 RECOMENDACIONES:")
print("-"*70)
print("\n1. Verifica que el número de variables en settings.py coincida")
print("2. Asegúrate de enviar exactamente ese número de variables")
print("3. Las variables deben ser strings")
print("4. El orden de las variables importa")

print("\n🔗 Verifica el estado de aprobación en:")
print("   https://console.twilio.com/us1/develop/sms/content-editor")

print("\n" + "="*70)
