# Crear estructura: frontend/management/commands/
# Y agregar este archivo

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Profile, Category, ProviderProfile, Service
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seed database with initial data'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱 Seeding database...')
        
        # Crear categorías
        beauty, _ = Category.objects.get_or_create(
            name='Belleza',
            defaults={
                'description': 'Servicios de belleza y cuidado personal',
                'icon': '💅'
            }
        )
        
        cleaning, _ = Category.objects.get_or_create(
            name='Limpieza',
            defaults={
                'description': 'Servicios de limpieza para hogar y oficina',
                'icon': '🧹'
            }
        )
        
        self.stdout.write('✅ Categorías creadas')
        
        # Crear proveedores de prueba
        providers_data = [
            {
                'username': 'maria_beauty',
                'email': 'maria@test.com',
                'first_name': 'María',
                'last_name': 'González',
                'category': beauty,
                'description': 'Especialista en manicure y pedicure con 5 años de experiencia',
                'services': [
                    {'name': 'Manicure', 'price': 15, 'duration': 60},
                    {'name': 'Pedicure', 'price': 20, 'duration': 90},
                ]
            },
            {
                'username': 'carlos_clean',
                'email': 'carlos@test.com',
                'first_name': 'Carlos',
                'last_name': 'Pérez',
                'category': cleaning,
                'description': 'Servicio profesional de limpieza para hogares y oficinas',
                'services': [
                    {'name': 'Limpieza de Hogar', 'price': 30, 'duration': 120},
                    {'name': 'Limpieza Profunda', 'price': 50, 'duration': 180},
                ]
            }
        ]
        
        for pdata in providers_data:
            user, created = User.objects.get_or_create(
                username=pdata['username'],
                defaults={
                    'email': pdata['email'],
                    'first_name': pdata['first_name'],
                    'last_name': pdata['last_name']
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
                
                Profile.objects.create(
                    user=user,
                    phone='0999888777',
                    role='provider',
                    verified=True
                )
                
                ProviderProfile.objects.create(
                    user=user,
                    category=pdata['category'],
                    description=pdata['description'],
                    coverage_zones=['Quito Norte', 'Centro', 'Cumbayá'],
                    avg_travel_cost=Decimal('3.00'),
                    status='approved'
                )
                
                # Crear servicios
                for sdata in pdata['services']:
                    Service.objects.create(
                        provider=user,
                        name=sdata['name'],
                        description=f"Servicio profesional de {sdata['name']}",
                        base_price=Decimal(str(sdata['price'])),
                        duration_minutes=sdata['duration'],
                        available=True
                    )
                
                self.stdout.write(f'✅ Proveedor creado: {user.username}')
        
        # Crear cliente de prueba
        customer, created = User.objects.get_or_create(
            username='cliente_test',
            defaults={
                'email': 'cliente@test.com',
                'first_name': 'Juan',
                'last_name': 'Cliente'
            }
        )
        
        if created:
            customer.set_password('password123')
            customer.save()
            
            Profile.objects.create(
                user=customer,
                phone='0988777666',
                role='customer',
                verified=True
            )
            
            self.stdout.write(f'✅ Cliente creado: {customer.username}')
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Seeding completado!'))
        self.stdout.write('\nCredenciales de prueba:')
        self.stdout.write('  Proveedor 1: maria_beauty / password123')
        self.stdout.write('  Proveedor 2: carlos_clean / password123')
        self.stdout.write('  Cliente: cliente_test / password123')