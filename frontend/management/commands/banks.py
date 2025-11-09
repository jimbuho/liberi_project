"""
Script para crear cuentas bancarias iniciales
Ejecutar con: python manage.py shell < init_bank_accounts.py
O desde el shell de Django: exec(open('init_bank_accounts.py').read())
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Bank  # Ajusta 'frontend' al nombre de tu app
from decimal import Decimal
from datetime import time, date, timedelta
from django.db import transaction

class Command(BaseCommand):
    help = 'Seed database with initial data including zones and schedules'

    def handle(self, *args, **kwargs):
        # Importar el modelo
        try:
            
            print("Creando bancos...")
            BANCOS_ECUADOR = [
                {'name': 'Banco Pichincha', 'code': 'BPC'},
                {'name': 'Banco del Pacifico', 'code': 'BDP'},
                {'name': 'Banco Guayaquil', 'code': 'BG'},
                {'name': 'Produbanco', 'code': 'PDB'},
                {'name': 'Banco Bolivariano', 'code': 'BB'},
                {'name': 'Banco Amazonas', 'code': 'BA'},
                {'name': 'Banco Internacional', 'code': 'BI'},
                {'name': 'Banco Austro', 'code': 'BAU'},
                {'name': 'Banco Solidario', 'code': 'BSO'},
                {'name': 'Banco 9 de Octubre', 'code': 'B9O'},
                {'name': 'Banco Finterra', 'code': 'BFI'},
                {'name': 'Industria Bank', 'code': 'IND'},
                {'name': 'Banco Machala', 'code': 'BM'},
                {'name': 'Banco Coopcentral', 'code': 'BC'},
            ]

            bancos = [
                ('Banco Pichincha', 'BPC'),
                ('Banco del Pacifico', 'BDP'),
                ('Banco Guayaquil', 'BG'),
                ('Produbanco', 'PDB'),
                ('Banco Bolivariano', 'BB'),
                ('Banco Amazonas', 'BA'),
                ('Banco Internacional', 'BI'),
                ('Banco Austro', 'BAU'),
                ('Banco Solidario', 'BSO'),
                ('Banco 9 de Octubre', 'B9O'),
                ('Banco Finterra', 'BFI'),
                ('Industria Bank', 'IND'),
                ('Banco Machala', 'BM'),
                ('Banco Coopcentral', 'BC'),
            ]

            with transaction.atomic():
                for name, code in bancos:
                    Bank.objects.get_or_create(name=name, code=code)

            print("\n✨ Bancos creados exitosamente!")
            print(f"🏦 Bancos: {Bank.objects.count()}")            
        except ImportError as e:
            print(f"Error: No se pudo importar el modelo Bank")
            print(f"Asegúrate de que el modelo existe en tu models.py")
            print(f"Detalle del error: {e}")
        except Exception as e:
            print(f"Error al crear bancos: {e}")
