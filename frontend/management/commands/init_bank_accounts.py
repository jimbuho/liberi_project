"""
Script para crear cuentas bancarias iniciales
Ejecutar con: python manage.py shell < init_bank_accounts.py
O desde el shell de Django: exec(open('init_bank_accounts.py').read())
"""

from django.db import transaction

# Importar el modelo
try:
    from core.models import BankAccount  # Ajusta 'frontend' al nombre de tu app
    
    print("Creando cuentas bancarias iniciales...")
    
    with transaction.atomic():
        # Limpiar cuentas existentes (opcional - comentar si no quieres esto)
        # BankAccount.objects.all().delete()
        
        # Cuenta 1: Banco Pichincha
        banco_pichincha, created = BankAccount.objects.get_or_create(
            account_number='2100123456',
            defaults={
                'bank_name': 'Banco Pichincha',
                'account_type': 'checking',
                'account_holder': 'Liberi Ecuador S.A.',
                'id_number': '1791234567001',
                'bank_code': '0001',
                'is_active': True,
                'display_order': 1,
                'notes': 'Cuenta principal para recibir pagos'
            }
        )
        if created:
            print(f"✓ Creada: {banco_pichincha}")
        else:
            print(f"○ Ya existe: {banco_pichincha}")
        
        # Cuenta 2: Banco Guayaquil
        banco_guayaquil, created = BankAccount.objects.get_or_create(
            account_number='0123456789',
            defaults={
                'bank_name': 'Banco Guayaquil',
                'account_type': 'savings',
                'account_holder': 'Liberi Ecuador S.A.',
                'id_number': '1791234567001',
                'bank_code': '0002',
                'is_active': True,
                'display_order': 2,
                'notes': 'Cuenta secundaria'
            }
        )
        if created:
            print(f"✓ Creada: {banco_guayaquil}")
        else:
            print(f"○ Ya existe: {banco_guayaquil}")
        
        # Cuenta 3: Banco del Pacífico
        banco_pacifico, created = BankAccount.objects.get_or_create(
            account_number='7654321098',
            defaults={
                'bank_name': 'Banco del Pacífico',
                'account_type': 'checking',
                'account_holder': 'Liberi Ecuador S.A.',
                'id_number': '1791234567001',
                'bank_code': '0003',
                'is_active': True,
                'display_order': 3,
                'notes': 'Cuenta terciaria'
            }
        )
        if created:
            print(f"✓ Creada: {banco_pacifico}")
        else:
            print(f"○ Ya existe: {banco_pacifico}")
    
    print("\n✓ Proceso completado!")
    print(f"\nTotal de cuentas activas: {BankAccount.objects.filter(is_active=True).count()}")
    
    # Listar todas las cuentas
    print("\nCuentas bancarias en el sistema:")
    for account in BankAccount.objects.all():
        status = "✓ Activa" if account.is_active else "✗ Inactiva"
        print(f"  {status} - {account.bank_name}: {account.account_number}")

except ImportError as e:
    print(f"Error: No se pudo importar el modelo BankAccount")
    print(f"Asegúrate de que el modelo existe en tu models.py")
    print(f"Detalle del error: {e}")
except Exception as e:
    print(f"Error al crear cuentas bancarias: {e}")

"""
INSTRUCCIONES DE USO:

1. Asegúrate de que el modelo BankAccount existe en tu models.py
2. Ejecuta las migraciones si no lo has hecho:
   python manage.py makemigrations
   python manage.py migrate

3. Ejecuta este script de una de estas formas:

   OPCIÓN A - Desde shell de Django:
   python manage.py shell
   >>> exec(open('init_bank_accounts.py').read())

   OPCIÓN B - Como comando:
   python manage.py shell < init_bank_accounts.py

   OPCIÓN C - Crear un management command (recomendado para producción)

4. Verifica en el admin que las cuentas se crearon correctamente
"""