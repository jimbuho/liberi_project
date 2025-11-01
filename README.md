# 🚀 Liberi MVP - Backend Django

Plataforma para conectar clientes con proveedores de servicios de belleza y limpieza en Ecuador.

## 📋 Requisitos

- Python 3.12+
- PostgreSQL (Supabase)
- Cuenta PayPhone Ecuador
- Cuenta Twilio WhatsApp (opcional)

## ⚡ Instalación Rápida

### 1. Clonar/Extraer el proyecto
```bash
cd liberi_mvp
```

### 2. Crear entorno virtual
```bash
# En Linux/Mac
python3 -m venv venv
source venv/bin/activate

# En Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tus credenciales
nano .env  # o usa tu editor favorito
```

**Variables importantes a configurar:**
```env
SECRET_KEY=genera-una-clave-secreta-aqui
DEBUG=True
DB_HOST=db.xxx.supabase.co
DB_PASSWORD=tu-password-supabase
PAYPHONE_TOKEN=tu-token-payphone
PAYPHONE_STORE_ID=tu-store-id
```

**Generar SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Configurar base de datos
```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario para admin
python manage.py createsuperuser
```

### 6. Cargar datos iniciales (opcional)
```bash
python manage.py shell
```
```python
from core.models import Category

# Crear categorías
Category.objects.create(
    name='Belleza',
    description='Servicios de belleza y cuidado personal',
    icon='💅'
)

Category.objects.create(
    name='Limpieza',
    description='Servicios de limpieza para hogar y oficina',
    icon='🧹'
)

exit()
```

### 7. Ejecutar servidor
```bash
python manage.py runserver
```

**Accede a:**
- 🌐 API: http://localhost:8000/api/
- 🎛️ Admin Panel: http://localhost:8000/admin/

---

## 📱 Endpoints API

### Autenticación

#### Registro
```bash
POST /api/register/
Content-Type: application/json

{
  "username": "juan123",
  "email": "juan@example.com",
  "password": "password123",
  "password_confirm": "password123",
  "phone": "0999999999",
  "role": "customer",  // customer, provider
  "first_name": "Juan",
  "last_name": "Pérez"
}
```

**Respuesta:**
```json
{
  "user": {
    "id": "uuid",
    "username": "juan123",
    "email": "juan@example.com",
    "role": "customer"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJh...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
  }
}
```

#### Login
```bash
POST /api/login/
Content-Type: application/json

{
  "username": "juan123",
  "password": "password123"
}
```

### Categorías
```bash
GET /api/categories/
```

### Servicios
```bash
# Listar servicios
GET /api/services/
GET /api/services/?category=belleza
GET /api/services/?min_price=10&max_price=50

# Crear servicio (solo proveedores)
POST /api/services/
Authorization: Bearer {token}

{
  "name": "Manicure completo",
  "description": "Incluye limado, esmaltado y decoración",
  "base_price": 15.00,
  "duration_minutes": 60,
  "available": true
}
```

### Proveedores
```bash
# Listar proveedores
GET /api/providers/
GET /api/providers/?status=approved
GET /api/providers/?category=belleza

# Crear perfil de proveedor
POST /api/providers/
Authorization: Bearer {token}

{
  "category": 1,
  "description": "Especialista en manicure con 5 años de experiencia",
  "coverage_zones": ["Quito Norte", "Cumbayá"],
  "avg_travel_cost": 5.00,
  "availability": {
    "monday": ["09:00-17:00"],
    "tuesday": ["09:00-17:00"]
  }
}

# Ver mi perfil de proveedor
GET /api/providers/me/
Authorization: Bearer {token}
```

### Ubicaciones
```bash
# Listar mis ubicaciones
GET /api/locations/
Authorization: Bearer {token}

# Crear ubicación
POST /api/locations/
Authorization: Bearer {token}

{
  "address": "Av. 6 de Diciembre y Wilson",
  "reference": "Edificio azul, Oficina 302",
  "label": "oficina",
  "latitude": -0.180653,
  "longitude": -78.467834
}
```

### Reservas
```bash
# Listar mis reservas
GET /api/bookings/
Authorization: Bearer {token}

# Crear reserva
POST /api/bookings/
Authorization: Bearer {token}

{
  "provider": "provider-uuid",
  "service_list": [
    {"service_id": 1, "name": "Manicure", "price": 15.00}
  ],
  "total_cost": 20.00,
  "location": 1,
  "scheduled_time": "2024-12-15T10:00:00Z",
  "notes": "Por favor traer colores suaves"
}

# Aceptar reserva (proveedor)
PATCH /api/bookings/{id}/accept/
Authorization: Bearer {token}

# Rechazar reserva (proveedor)
PATCH /api/bookings/{id}/reject/
Authorization: Bearer {token}

# Completar reserva (proveedor)
PATCH /api/bookings/{id}/complete/
Authorization: Bearer {token}
```

### Pagos
```bash
# Crear pago PayPhone
POST /api/payments/payphone/create/
Authorization: Bearer {token}

{
  "booking_id": "booking-uuid"
}

# Verificar pago
POST /api/payments/payphone/verify/
Authorization: Bearer {token}

{
  "booking_id": "booking-uuid",
  "transaction_id": "txn-id"
}

# Registrar transferencia bancaria
POST /api/payments/bank-transfer/
Authorization: Bearer {token}

{
  "booking_id": "booking-uuid",
  "reference": "REF123456"
}
```

### Reseñas
```bash
# Listar reseñas
GET /api/reviews/
GET /api/reviews/?provider=provider-uuid

# Crear reseña
POST /api/reviews/
Authorization: Bearer {token}

{
  "booking": "booking-uuid",
  "rating": 5,
  "comment": "Excelente servicio, muy profesional"
}
```

---

## 🎛️ Panel de Administración

Accede a `http://localhost:8000/admin/` con tu superusuario.

### Funcionalidades:

✅ **Gestión de Usuarios**
- Ver todos los usuarios registrados
- Verificar usuarios manualmente
- Cambiar roles

✅ **Aprobación de Proveedores**
- Ver perfiles de proveedores pendientes
- Aprobar/rechazar proveedores en lote
- Ver documentos cargados

✅ **Gestión de Reservas**
- Monitorear todas las reservas
- Ver estados de pago
- Resolver disputas

✅ **Logs de Auditoría**
- Ver todas las acciones del sistema
- Rastrear cambios importantes

---

## 🧪 Pruebas

### 1. Probar con cURL
```bash
# Registro de usuario
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test",
    "email": "test@example.com",
    "password": "test1234",
    "password_confirm": "test1234",
    "phone": "0999999999",
    "role": "customer"
  }'

# Login
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test",
    "password": "test1234"
  }'

# Listar categorías
curl http://localhost:8000/api/categories/
```

### 2. Probar con Postman

1. Importa la colección (crear archivo `Liberi.postman_collection.json`)
2. Configura el environment con la URL base: `http://localhost:8000`
3. Ejecuta los requests en orden

### 3. Crear datos de prueba
```bash
python manage.py shell
```
```python
from core.models import User, Category, Service, ProviderProfile
from django.utils import timezone
from datetime import timedelta

# Crear proveedor
provider = User.objects.create_user(
    username='maria_nails',
    email='maria@example.com',
    password='password123',
    phone='0999888777',
    role='provider',
    first_name='María',
    last_name='González',
    verified=True
)

# Crear categoría
beauty = Category.objects.get_or_create(
    name='Belleza',
    defaults={'description': 'Servicios de belleza', 'icon': '💅'}
)[0]

# Crear perfil de proveedor
profile = ProviderProfile.objects.create(
    user=provider,
    category=beauty,
    description='Especialista en manicure y pedicure',
    coverage_zones=['Quito Norte', 'Centro'],
    avg_travel_cost=3.00,
    availability={'monday': ['09:00-17:00']},
    status='approved'
)

# Crear servicios
Service.objects.create(
    provider=provider,
    name='Manicure',
    description='Manicure completo',
    base_price=15.00,
    duration_minutes=60,
    available=True
)

Service.objects.create(
    provider=provider,
    name='Pedicure',
    description='Pedicure completo con masaje',
    base_price=20.00,
    duration_minutes=90,
    available=True
)

print("✅ Datos de prueba creados!")
exit()
```

---

## 🚀 Despliegue en Fly.io

### 1. Instalar Fly CLI
```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

### 2. Autenticarse
```bash
fly auth login
```

### 3. Configurar secretos
```bash
fly secrets set SECRET_KEY="tu-secret-key"
fly secrets set DB_PASSWORD="tu-password-supabase"
fly secrets set DB_HOST="db.xxx.supabase.co"
fly secrets set PAYPHONE_TOKEN="tu-token"
fly secrets set PAYPHONE_STORE_ID="tu-store-id"
fly secrets set DEBUG="False"
```

### 4. Lanzar aplicación
```bash
fly launch
```

### 5. Desplegar
```bash
fly deploy
```

### 6. Ver logs
```bash
fly logs
```

---

## 🔧 Comandos Útiles
```bash
# Ver logs del servidor
python manage.py runserver --verbosity 2

# Crear backup de base de datos
python manage.py dumpdata > backup.json

# Restaurar backup
python manage.py loaddata backup.json

# Crear migraciones
python manage.py makemigrations

# Ver SQL de migraciones
python manage.py sqlmigrate core 0001

# Shell interactivo
python manage.py shell

# Recolectar archivos estáticos
python manage.py collectstatic

# Verificar proyecto
python manage.py check
```

---

## 🐛 Solución de Problemas

### Error: "No module named 'dotenv'"
```bash
pip install python-dotenv
```

### Error de conexión a PostgreSQL
```bash
# Verificar credenciales en .env
# Probar conexión:
psql -h db.xxx.supabase.co -U postgres -d postgres
```

### Error: "Table doesn't exist"
```bash
python manage.py migrate
```

### Puerto 8000 ocupado
```bash
python manage.py runserver 8001
```

### Resetear migraciones
```bash
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc"  -delete
python manage.py makemigrations
python manage.py migrate
```

---

## 📚 Recursos

- [Documentación Django](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PayPhone API Docs](https://developers.payphone.app/)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [Supabase](https://supabase.com/docs)

---

## 📞 Soporte

Para problemas o dudas:
1. Revisa la documentación
2. Verifica los logs: `python manage.py runserver --verbosity 2`
3. Consulta el admin panel para verificar datos

---

**Liberi MVP** | Conectando servicios con calidad 🇪🇨
