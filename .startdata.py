from django.contrib.auth.models import User
from core.models import Profile, Category, ProviderProfile, Service

# Crear categorías
beauty = Category.objects.create(name='Belleza', description='Servicios de belleza', icon='💅')
cleaning = Category.objects.create(name='Limpieza', description='Servicios de limpieza', icon='🧹')

# Crear proveedor
provider = User.objects.create_user(username='maria_nails', email='maria@example.com', password='password123', first_name='María', last_name='González')
Profile.objects.create(user=provider, phone='0999888777', role='provider', verified=True)
ProviderProfile.objects.create(user=provider, category=beauty, description='Especialista en manicure', coverage_zones=['Quito Norte'], avg_travel_cost=3.00, availability={'monday': ['09:00-17:00']}, status='approved')
Service.objects.create(provider=provider, name='Manicure', description='Manicure completo', base_price=15.00, duration_minutes=60, available=True)

# Crear cliente
customer = User.objects.create_user(username='juan_cliente', email='juan@example.com', password='password123', first_name='Juan', last_name='Pérez')
Profile.objects.create(user=customer, phone='0988777666', role='customer', verified=True)

print("✅ Datos creados!")
exit()
