from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Profile, Category, ProviderProfile, Service, Zone, 
    ProviderSchedule, ProviderUnavailability
)
from decimal import Decimal
from datetime import time, date, timedelta

class Command(BaseCommand):
    help = 'Seed database with initial data including zones and schedules'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱 Seeding database...')
        
        # 1. Crear Zonas de Quito
        self.stdout.write('📍 Creando zonas...')
        zones_data = [
            {'name': 'Quito Norte', 'city': 'Quito', 'description': 'Sector norte de Quito'},
            {'name': 'Quito Centro', 'city': 'Quito', 'description': 'Centro histórico y alrededores'},
            {'name': 'Quito Sur', 'city': 'Quito', 'description': 'Sector sur de Quito'},
            {'name': 'Cumbayá', 'city': 'Quito', 'description': 'Valle de Cumbayá'},
            {'name': 'Tumbaco', 'city': 'Quito', 'description': 'Valle de Tumbaco'},
            {'name': 'Los Chillos', 'city': 'Quito', 'description': 'Valle de Los Chillos'},
            {'name': 'Calderón', 'city': 'Quito', 'description': 'Sector Calderón'},
            {'name': 'Conocoto', 'city': 'Quito', 'description': 'Sector Conocoto'},
        ]
        
        zones = {}
        for zone_data in zones_data:
            zone, created = Zone.objects.get_or_create(
                name=zone_data['name'],
                defaults={
                    'city': zone_data['city'],
                    'description': zone_data['description'],
                    'active': True
                }
            )
            zones[zone_data['name']] = zone
            if created:
                self.stdout.write(f'  ✅ Zona creada: {zone.name}')
        
        # 2. Crear categorías
        self.stdout.write('\n📂 Creando categorías...')
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
        
        self.stdout.write('  ✅ Categorías creadas')
        
        # 3. Crear proveedores de prueba con horarios
        self.stdout.write('\n👥 Creando proveedores...')
        providers_data = [
            {
                'username': 'maria_beauty',
                'email': 'maria@test.com',
                'first_name': 'María',
                'last_name': 'González',
                'phone': '0999888777',
                'category': beauty,
                'description': 'Especialista en manicure y pedicure con 5 años de experiencia. Uso productos de alta calidad y técnicas profesionales.',
                'zones': ['Quito Norte', 'Quito Centro', 'Cumbayá'],
                'avg_travel_cost': Decimal('3.00'),
                'services': [
                    {
                        'name': 'Manicure Clásico',
                        'description': 'Manicure completo con esmaltado tradicional, incluye limado, cutícula y hidratación',
                        'price': 15,
                        'duration': 60
                    },
                    {
                        'name': 'Manicure con Gel',
                        'description': 'Manicure con esmaltado en gel de larga duración (hasta 3 semanas)',
                        'price': 25,
                        'duration': 90
                    },
                    {
                        'name': 'Pedicure Spa',
                        'description': 'Pedicure completo con exfoliación, masaje y esmaltado',
                        'price': 20,
                        'duration': 90
                    },
                ],
                'schedule': [
                    # Lunes a Viernes: 9am-1pm y 3pm-7pm
                    {'day': 0, 'start': '09:00', 'end': '13:00'},
                    {'day': 0, 'start': '15:00', 'end': '19:00'},
                    {'day': 1, 'start': '09:00', 'end': '13:00'},
                    {'day': 1, 'start': '15:00', 'end': '19:00'},
                    {'day': 2, 'start': '09:00', 'end': '13:00'},
                    {'day': 2, 'start': '15:00', 'end': '19:00'},
                    {'day': 3, 'start': '09:00', 'end': '13:00'},
                    {'day': 3, 'start': '15:00', 'end': '19:00'},
                    {'day': 4, 'start': '09:00', 'end': '13:00'},
                    {'day': 4, 'start': '15:00', 'end': '19:00'},
                    # Sábado: 10am-4pm
                    {'day': 5, 'start': '10:00', 'end': '16:00'},
                ]
            },
            {
                'username': 'carlos_clean',
                'email': 'carlos@test.com',
                'first_name': 'Carlos',
                'last_name': 'Pérez',
                'phone': '0988777666',
                'category': cleaning,
                'description': 'Servicio profesional de limpieza para hogares y oficinas. 8 años de experiencia, equipo propio y productos ecológicos.',
                'zones': ['Quito Norte', 'Quito Centro', 'Quito Sur', 'Cumbayá'],
                'avg_travel_cost': Decimal('5.00'),
                'services': [
                    {
                        'name': 'Limpieza Básica de Hogar',
                        'description': 'Limpieza general de hogar: pisos, baños, cocina, desempolvado',
                        'price': 30,
                        'duration': 120
                    },
                    {
                        'name': 'Limpieza Profunda',
                        'description': 'Limpieza profunda con desinfección completa, incluye áreas difíciles',
                        'price': 50,
                        'duration': 180
                    },
                    {
                        'name': 'Limpieza de Oficina',
                        'description': 'Limpieza de espacios de trabajo, escritorios y áreas comunes',
                        'price': 40,
                        'duration': 150
                    },
                ],
                'schedule': [
                    # Lunes a Sábado: 8am-5pm
                    {'day': 0, 'start': '08:00', 'end': '17:00'},
                    {'day': 1, 'start': '08:00', 'end': '17:00'},
                    {'day': 2, 'start': '08:00', 'end': '17:00'},
                    {'day': 3, 'start': '08:00', 'end': '17:00'},
                    {'day': 4, 'start': '08:00', 'end': '17:00'},
                    {'day': 5, 'start': '08:00', 'end': '17:00'},
                ]
            },
            {
                'username': 'ana_stylist',
                'email': 'ana@test.com',
                'first_name': 'Ana',
                'last_name': 'Morales',
                'phone': '0997766555',
                'category': beauty,
                'description': 'Estilista profesional especializada en cortes, peinados y tratamientos capilares. 10 años de experiencia.',
                'zones': ['Cumbayá', 'Tumbaco', 'Quito Norte'],
                'avg_travel_cost': Decimal('4.00'),
                'services': [
                    {
                        'name': 'Corte de Cabello Mujer',
                        'description': 'Corte personalizado según tipo de rostro y estilo',
                        'price': 18,
                        'duration': 60
                    },
                    {
                        'name': 'Peinado para Eventos',
                        'description': 'Peinado elegante para bodas, graduaciones y eventos especiales',
                        'price': 35,
                        'duration': 90
                    },
                    {
                        'name': 'Tratamiento Capilar',
                        'description': 'Tratamiento de hidratación profunda y restauración',
                        'price': 25,
                        'duration': 75
                    },
                ],
                'schedule': [
                    # Martes a Domingo: 10am-7pm (descansa lunes)
                    {'day': 1, 'start': '10:00', 'end': '19:00'},
                    {'day': 2, 'start': '10:00', 'end': '19:00'},
                    {'day': 3, 'start': '10:00', 'end': '19:00'},
                    {'day': 4, 'start': '10:00', 'end': '19:00'},
                    {'day': 5, 'start': '10:00', 'end': '19:00'},
                    {'day': 6, 'start': '10:00', 'end': '19:00'},
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
                
                # Crear perfil
                Profile.objects.create(
                    user=user,
                    phone=pdata['phone'],
                    role='provider',
                    verified=True
                )
                
                # Crear perfil de proveedor
                provider_profile = ProviderProfile.objects.create(
                    user=user,
                    category=pdata['category'],
                    description=pdata['description'],
                    avg_travel_cost=pdata['avg_travel_cost'],
                    status='approved',
                    is_active=True
                )
                
                # Asignar zonas
                for zone_name in pdata['zones']:
                    provider_profile.coverage_zones.add(zones[zone_name])
                
                # Crear horarios
                for schedule in pdata['schedule']:
                    ProviderSchedule.objects.create(
                        provider=user,
                        day_of_week=schedule['day'],
                        start_time=time.fromisoformat(schedule['start']),
                        end_time=time.fromisoformat(schedule['end']),
                        is_active=True
                    )
                
                # Crear servicios
                for sdata in pdata['services']:
                    Service.objects.create(
                        provider=user,
                        name=sdata['name'],
                        description=sdata['description'],
                        base_price=Decimal(str(sdata['price'])),
                        duration_minutes=sdata['duration'],
                        available=True
                    )
                
                self.stdout.write(f'  ✅ Proveedor creado: {user.username}')
        
        # 4. Crear cliente de prueba
        self.stdout.write('\n👤 Creando cliente de prueba...')
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
            
            self.stdout.write(f'  ✅ Cliente creado: {customer.username}')
        
        # 5. Crear ejemplo de inactividad (opcional)
        self.stdout.write('\n🗓️  Creando ejemplo de inactividad...')
        # María toma vacaciones en 15 días
        maria = User.objects.get(username='maria_beauty')
        future_date = date.today() + timedelta(days=15)
        ProviderUnavailability.objects.get_or_create(
            provider=maria,
            start_date=future_date,
            end_date=future_date + timedelta(days=7),
            defaults={'reason': 'Vacaciones programadas'}
        )
        self.stdout.write('  ✅ Ejemplo de inactividad creado')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n🎉 Seeding completado!'))
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 RESUMEN:')
        self.stdout.write(f'  • Zonas: {Zone.objects.count()}')
        self.stdout.write(f'  • Categorías: {Category.objects.count()}')
        self.stdout.write(f'  • Proveedores: {ProviderProfile.objects.count()}')
        self.stdout.write(f'  • Servicios: {Service.objects.count()}')
        self.stdout.write(f'  • Horarios: {ProviderSchedule.objects.count()}')
        self.stdout.write(f'  • Clientes: {Profile.objects.filter(role="customer").count()}')
        self.stdout.write('='*60)
        self.stdout.write('\n🔑 CREDENCIALES DE PRUEBA:')
        self.stdout.write('  Proveedores:')
        self.stdout.write('    • maria_beauty / password123 (Belleza - Quito Norte)')
        self.stdout.write('    • carlos_clean / password123 (Limpieza - Multi-zona)')
        self.stdout.write('    • ana_stylist / password123 (Belleza - Valles)')
        self.stdout.write('  Cliente:')
        self.stdout.write('    • cliente_test / password123')
        self.stdout.write('='*60 + '\n')