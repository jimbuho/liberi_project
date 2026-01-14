#!/usr/bin/env python
"""
Script para verificar el estado de un mensaje de WhatsApp en Twilio
Uso: python check_message_status.py [MESSAGE_SID]
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.whatsapp_notifications.services import WhatsAppService

def main():
    if len(sys.argv) < 2:
        print("❌ Error: Debes proporcionar un Message SID")
        print("\nUso:")
        print("  python check_message_status.py SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("\nEjemplo:")
        print("  python check_message_status.py SM15ddc95f104ef7a8fac70ccb86768fab")
        sys.exit(1)
    
    message_sid = sys.argv[1]
    
    print("="*70)
    print(f"🔍 VERIFICANDO ESTADO DEL MENSAJE")
    print("="*70)
    print(f"\n📱 Message SID: {message_sid}\n")
    
    result = WhatsAppService.check_message_status(message_sid)
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}\n")
        sys.exit(1)
    
    # Mapeo de estados a emojis
    status_emoji = {
        'queued': '⏳',
        'sent': '📤',
        'delivered': '✅',
        'read': '👁️',
        'failed': '❌',
        'undelivered': '⚠️',
    }
    
    emoji = status_emoji.get(result['status'], '❓')
    
    print(f"{emoji} Estado: {result['status'].upper()}")
    print("-"*70)
    
    print(f"\n📊 Detalles:")
    print(f"   Desde: {result['from']}")
    print(f"   Para: {result['to']}")
    print(f"   Enviado: {result['date_sent']}")
    print(f"   Actualizado: {result['date_updated']}")
    
    if result['price']:
        print(f"   Costo: {result['price']} {result['price_unit']}")
    
    if result['error_code']:
        print(f"\n❌ Error:")
        print(f"   Código: {result['error_code']}")
        print(f"   Mensaje: {result['error_message']}")
        
        # Diagnóstico del error
        error_hints = {
            63051: "El número destinatario no está activado en el Sandbox o el remitente no está configurado",
            63016: "El número destinatario no tiene WhatsApp instalado",
            63007: "Template no aprobado o variables incorrectas",
            21211: "El número no está en el sandbox. Envía 'join [codigo]' al número de Twilio",
        }
        
        hint = error_hints.get(result['error_code'])
        if hint:
            print(f"\n💡 Solución sugerida:")
            print(f"   {hint}")
    else:
        print(f"\n✅ Sin errores")
    
    print("\n" + "="*70)
    
    # Interpretación del estado
    if result['status'] == 'delivered':
        print("🎉 ¡Mensaje entregado exitosamente!")
    elif result['status'] == 'sent':
        print("⏳ Mensaje enviado, esperando confirmación de entrega...")
    elif result['status'] == 'failed':
        print("❌ El mensaje falló. Revisa el código de error arriba.")
    elif result['status'] == 'undelivered':
        print("⚠️ El mensaje no pudo ser entregado. Revisa el código de error arriba.")
    
    print("="*70)
    print()

if __name__ == '__main__':
    main()
