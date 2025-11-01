from django.db import models
from django.contrib.auth.models import User
import uuid

# Extender el User de Django con un Profile
class Profile(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Cliente'),
        ('provider', 'Proveedor'),
        ('admin', 'Administrador'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='Usuario')
    phone = models.CharField('Teléfono', max_length=20, blank=True)
    role = models.CharField('Rol', max_length=10, choices=ROLE_CHOICES, default='customer')
    verified = models.BooleanField('Verificado', default=False)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'profiles'
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class Category(models.Model):
    name = models.CharField('Nombre', max_length=100)
    description = models.TextField('Descripción', blank=True)
    icon = models.CharField('Icono', max_length=50, blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProviderProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, 
                                related_name='provider_profile', verbose_name='Usuario')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, 
                                 verbose_name='Categoría')
    description = models.TextField('Descripción')
    coverage_zones = models.ManyToManyField('Zone', verbose_name='Zonas de cobertura',  # ← CAMBIAR
                                           related_name='providers')
    avg_travel_cost = models.DecimalField('Costo promedio de traslado', max_digits=6, 
                                          decimal_places=2, default=0)
    availability = models.JSONField('Disponibilidad', default=dict)
    status = models.CharField('Estado', max_length=10, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField('Activo', default=True)  # ← AGREGAR
    signed_contract_url = models.URLField('URL del contrato firmado', blank=True)
    id_card_front = models.ImageField('Cédula frontal', upload_to='documents/', blank=True)
    id_card_back = models.ImageField('Cédula posterior', upload_to='documents/', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'provider_profiles'
        verbose_name = 'Perfil de Proveedor'
        verbose_name_plural = 'Perfiles de Proveedores'

    def __str__(self):
        return f"{self.user.username} - {self.category}"


class Service(models.Model):
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='services',
                                verbose_name='Proveedor')
    name = models.CharField('Nombre', max_length=200)
    description = models.TextField('Descripción')
    base_price = models.DecimalField('Precio base', max_digits=8, decimal_places=2)
    duration_minutes = models.IntegerField('Duración (minutos)')
    available = models.BooleanField('Disponible', default=True)
    image = models.ImageField('Imagen', upload_to='services/', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'services'
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - ${self.base_price}"


class Location(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations',
                                verbose_name='Cliente')
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True,  # ← AGREGAR
                            verbose_name='Zona')
    address = models.TextField('Dirección')
    reference = models.CharField('Referencia', max_length=255, blank=True)
    label = models.CharField('Etiqueta', max_length=50, default='casa')
    latitude = models.DecimalField('Latitud', max_digits=9, decimal_places=6)  # ← REQUERIDO
    longitude = models.DecimalField('Longitud', max_digits=9, decimal_places=6)  # ← REQUERIDO
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'locations'
        verbose_name = 'Ubicación'
        verbose_name_plural = 'Ubicaciones'

    def __str__(self):
        return f"{self.customer.username} - {self.label}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptado'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('dispute', 'Disputa'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('failed', 'Fallido'),
        ('refunded', 'Reembolsado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_bookings',
                                verbose_name='Cliente')
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_bookings',
                                verbose_name='Proveedor')
    service_list = models.JSONField('Lista de servicios', default=list)
    total_cost = models.DecimalField('Costo total', max_digits=10, decimal_places=2)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True,
                                verbose_name='Ubicación')
    status = models.CharField('Estado', max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField('Estado de pago', max_length=20, 
                                     choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField('Método de pago', max_length=50, blank=True)
    scheduled_time = models.DateTimeField('Hora programada')
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'bookings'
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reserva {str(self.id)[:8]} - {self.get_status_display()}"


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review',
                                  verbose_name='Reserva')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Cliente')
    rating = models.IntegerField('Calificación', choices=[(i, f'{i} estrellas') for i in range(1, 6)])
    comment = models.TextField('Comentario', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'reviews'
        verbose_name = 'Reseña'
        verbose_name_plural = 'Reseñas'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reseña - {self.rating}⭐"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                           verbose_name='Usuario')
    action = models.CharField('Acción', max_length=255)
    timestamp = models.DateTimeField('Fecha y hora', auto_now_add=True)
    metadata = models.JSONField('Metadatos', default=dict)
    ip_address = models.GenericIPAddressField('Dirección IP', null=True, blank=True)

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
class Zone(models.Model):
    """Zonas geográficas para matching cliente-proveedor"""
    name = models.CharField('Nombre', max_length=100, unique=True)
    description = models.TextField('Descripción', blank=True)
    city = models.CharField('Ciudad', max_length=100, default='Quito')
    active = models.BooleanField('Activa', default=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'zones'
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.name} - {self.city}"
    
class ProviderSchedule(models.Model):
    """Horarios disponibles del proveedor"""
    DAYS_OF_WEEK = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    provider = models.ForeignKey(User, on_delete=models.CASCADE, 
                                related_name='schedules', verbose_name='Proveedor')
    day_of_week = models.IntegerField('Día de la semana', choices=DAYS_OF_WEEK)
    start_time = models.TimeField('Hora inicio')
    end_time = models.TimeField('Hora fin')
    is_active = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'provider_schedules'
        verbose_name = 'Horario de Proveedor'
        verbose_name_plural = 'Horarios de Proveedores'
        unique_together = ['provider', 'day_of_week', 'start_time']
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.provider.username} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class ProviderUnavailability(models.Model):
    """Días de inactividad/vacaciones del proveedor"""
    provider = models.ForeignKey(User, on_delete=models.CASCADE, 
                                related_name='unavailabilities', verbose_name='Proveedor')
    start_date = models.DateField('Fecha inicio')
    end_date = models.DateField('Fecha fin')
    reason = models.CharField('Motivo', max_length=255, blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'provider_unavailabilities'
        verbose_name = 'Inactividad de Proveedor'
        verbose_name_plural = 'Inactividades de Proveedores'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.provider.username} - {self.start_date} a {self.end_date}"