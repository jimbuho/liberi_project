from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.core.validators import RegexValidator

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
        ('pending_validation', 'Pendiente de Validación'),
        ('paid', 'Pagado'),
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

    def get_services_display(self):
        """
        Retorna una representación legible de los servicios
        """
        if isinstance(self.service_list, list):
            return ', '.join([s.get('name', '') for s in self.service_list])
        return 'N/A'

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
    
class SystemConfig(models.Model):
    """Configuraciones parametrizables del sistema"""
    key = models.CharField('Clave', max_length=100, unique=True)
    value = models.TextField('Valor')
    description = models.TextField('Descripción', blank=True)
    value_type = models.CharField('Tipo de Valor', max_length=20, 
                                   choices=[
                                       ('string', 'Texto'),
                                       ('integer', 'Número Entero'),
                                       ('decimal', 'Número Decimal'),
                                       ('boolean', 'Verdadero/Falso'),
                                   ], default='string')
    updated_at = models.DateTimeField('Última actualización', auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   verbose_name='Actualizado por')

    class Meta:
        db_table = 'system_config'
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuraciones del Sistema'
        ordering = ['key']

    def __str__(self):
        return f"{self.key}: {self.value}"

    def get_value(self):
        """Convierte el valor al tipo correcto"""
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'decimal':
            from decimal import Decimal
            return Decimal(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'si')
        return self.value

    @classmethod
    def get_config(cls, key, default=None):
        """Obtiene una configuración por su clave"""
        try:
            config = cls.objects.get(key=key)
            return config.get_value()
        except cls.DoesNotExist:
            return default


class ProviderZoneCost(models.Model):
    """Costos de movilización por zona para cada proveedor"""
    provider = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='zone_costs',
                                verbose_name='Proveedor')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE,
                            verbose_name='Zona')
    travel_cost = models.DecimalField('Costo de traslado', max_digits=6, 
                                      decimal_places=2, default=0)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'provider_zone_costs'
        verbose_name = 'Costo de Zona'
        verbose_name_plural = 'Costos por Zona'
        unique_together = ['provider', 'zone']
        ordering = ['provider', 'zone']

    def __str__(self):
        return f"{self.provider.username} - {self.zone.name}: ${self.travel_cost}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Validar que no exceda el máximo configurado
        max_cost = SystemConfig.get_config('max_travel_cost', 5)
        if self.travel_cost > max_cost:
            raise ValidationError(
                f'El costo de traslado no puede superar ${max_cost} USD'
            )

class PaymentMethod(models.Model):
    """
    Modelo para gestionar los métodos de pago disponibles en la plataforma
    """
    PAYMENT_METHOD_CHOICES = [
        ('payphone', 'PayPhone'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('credit_card', 'Tarjeta de Crédito'),
        ('cash', 'Efectivo'),
    ]
    
    name = models.CharField(
        max_length=100, 
        verbose_name='Nombre del Método'
    )
    code = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name='Código',
        help_text='Código único para identificar el método (ej: payphone, bank_transfer)'
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Descripción',
        help_text='Descripción que verá el usuario'
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name='Activo',
        help_text='Activar/Desactivar este método de pago'
    )
    requires_proof = models.BooleanField(
        default=False, 
        verbose_name='Requiere Comprobante',
        help_text='¿Este método requiere que el usuario suba una imagen de comprobante?'
    )
    requires_reference = models.BooleanField(
        default=False, 
        verbose_name='Requiere Referencia',
        help_text='¿Este método requiere un código de referencia o número de transacción?'
    )
    display_order = models.IntegerField(
        default=0, 
        verbose_name='Orden de Visualización',
        help_text='Orden en que aparecerá en la lista (menor número = primero)'
    )
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name='Ícono',
        help_text='Emoji o código de ícono (ej: 💳, 🏦)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Método de Pago'
        verbose_name_plural = 'Métodos de Pago'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return f"{self.name} {'(Activo)' if self.is_active else '(Inactivo)'}"


# ============================================
# MODELO: BankAccount
# ============================================

class BankAccount(models.Model):
    """
    Modelo para almacenar las cuentas bancarias de la empresa
    donde los clientes pueden realizar transferencias
    """
    ACCOUNT_TYPE_CHOICES = [
        ('savings', 'Cuenta de Ahorros'),
        ('checking', 'Cuenta Corriente'),
    ]
    
    bank_name = models.CharField(
        max_length=100,
        verbose_name='Nombre del Banco',
        help_text='Ej: Banco Pichincha, Banco Guayaquil'
    )
    
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default='checking',
        verbose_name='Tipo de Cuenta'
    )
    
    account_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Número de Cuenta',
        help_text='Número de cuenta bancaria'
    )
    
    account_holder = models.CharField(
        max_length=200,
        verbose_name='Titular de la Cuenta',
        help_text='Nombre completo o razón social del titular'
    )
    
    id_number = models.CharField(
        max_length=20,
        verbose_name='RUC/Cédula',
        help_text='Número de identificación del titular (RUC o Cédula)',
        validators=[
            RegexValidator(
                regex=r'^\d{10,13}$',
                message='Ingrese un número de cédula o RUC válido (10-13 dígitos)'
            )
        ]
    )
    
    swift_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Código SWIFT/BIC',
        help_text='Código internacional del banco (opcional)'
    )
    
    bank_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='Código del Banco',
        help_text='Código identificador del banco'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Si está activa, se mostrará a los clientes para realizar transferencias'
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización',
        help_text='Orden en que se muestra (menor número = primero)'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas',
        help_text='Notas internas sobre esta cuenta (no visible para clientes)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'bank_name']
        verbose_name = 'Cuenta Bancaria'
        verbose_name_plural = 'Cuentas Bancarias'
    
    def __str__(self):
        return f"{self.bank_name} - {self.get_account_type_display()} ({self.account_number})"
    
    def get_masked_account_number(self):
        """
        Retorna el número de cuenta parcialmente enmascarado
        Ej: 2100123456 -> 2100****3456
        """
        if len(self.account_number) > 8:
            return f"{self.account_number[:4]}{'*' * (len(self.account_number) - 8)}{self.account_number[-4:]}"
        return self.account_number


# ============================================
# MODELO: PaymentProof
# ============================================

class PaymentProof(models.Model):
    """
    Modelo para almacenar los comprobantes de pago subidos por los usuarios
    """
    booking = models.ForeignKey(
        'Booking',  # Asume que ya tienes un modelo Booking
        on_delete=models.CASCADE,
        related_name='payment_proofs',
        verbose_name='Reserva'
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        verbose_name='Método de Pago'
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Cuenta Bancaria',
        help_text='Cuenta bancaria a la que se realizó la transferencia'
    )
    reference_code = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name='Código de Referencia',
        help_text='Número de comprobante o referencia de la transacción'
    )
    proof_image = models.ImageField(
        upload_to='payment_proofs/',
        blank=True,
        null=True,
        verbose_name='Comprobante de Pago',
        help_text='Imagen o foto del comprobante de pago'
    )
    verified = models.BooleanField(
        default=False, 
        verbose_name='Verificado',
        help_text='¿El pago ha sido verificado por un administrador?'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='verified_payments',
        verbose_name='Verificado Por'
    )
    verified_at = models.DateTimeField(
        blank=True, 
        null=True, 
        verbose_name='Fecha de Verificación'
    )
    notes = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Notas del Admin',
        help_text='Notas internas del administrador sobre este pago'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Comprobante de Pago'
        verbose_name_plural = 'Comprobantes de Pago'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'verified']),
        ]
    
    def __str__(self):
        return f"Comprobante #{self.id} - Reserva #{self.booking.id} - {'Verificado' if self.verified else 'Pendiente'}"


# ============================================
# MODELO: Notification
# ============================================

class Notification(models.Model):
    """
    Modelo para gestionar las notificaciones de usuarios
    """
    NOTIFICATION_TYPES = [
        ('booking_created', 'Nueva Reserva'),
        ('booking_accepted', 'Reserva Aceptada'),
        ('booking_rejected', 'Reserva Rechazada'),
        ('booking_completed', 'Reserva Completada'),
        ('payment_received', 'Pago Recibido'),
        ('payment_verified', 'Pago Verificado'),
        ('review_received', 'Nueva Reseña'),
        ('system', 'Notificación del Sistema'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Usuario'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        verbose_name='Tipo'
    )
    title = models.CharField(
        max_length=200, 
        verbose_name='Título'
    )
    message = models.TextField(
        verbose_name='Mensaje'
    )
    is_read = models.BooleanField(
        default=False, 
        verbose_name='Leída'
    )
    booking = models.ForeignKey(
        'Booking',  # Asume que ya tienes un modelo Booking
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name='Reserva Relacionada'
    )
    action_url = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        verbose_name='URL de Acción',
        help_text='URL a la que se redirigirá al hacer clic en la notificación'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title} - {'Leída' if self.is_read else 'No leída'}"
    
    def mark_as_read(self):
        """Marca la notificación como leída"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


class Payment(models.Model):
    """
    Modelo para gestionar los pagos de las reservas
    """
    PAYMENT_METHOD_CHOICES = [
        ('payphone', 'PayPhone'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('cash', 'Efectivo'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('pending_validation', 'Pendiente de Validación'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('refunded', 'Reembolsado'),
        ('cancelled', 'Cancelado'),
    ]
    
    booking = models.ForeignKey(
        'Booking', 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Monto del pago'
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES,
        default='payphone'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='pending'
    )
    transaction_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='ID de transacción del procesador de pagos'
    )
    
    # Campos específicos para transferencia bancaria
    reference_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Número de referencia de la transferencia'
    )
    transfer_date = models.DateField(
        blank=True, 
        null=True,
        help_text='Fecha en que se realizó la transferencia'
    )
    transfer_receipt = models.FileField(
        upload_to='payment_receipts/', 
        blank=True, 
        null=True,
        help_text='Comprobante de la transferencia'
    )
    
    # Campos adicionales
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text='Notas adicionales sobre el pago'
    )
    validated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='validated_payments',
        help_text='Administrador que validó el pago'
    )
    validated_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text='Fecha y hora de validación'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
    
    def __str__(self):
        return f"Pago #{self.id} - Reserva #{self.booking.id} - ${self.amount}"
    
    def mark_as_completed(self, validated_by=None):
        """
        Marca el pago como completado y actualiza la reserva
        """
        self.status = 'completed'
        self.validated_by = validated_by
        self.validated_at = timezone.now()
        self.save()
        
        # Actualizar el estado de pago de la reserva
        self.booking.payment_status = 'paid'
        self.booking.save()
        
        # Enviar notificación al cliente
        self.send_payment_approved_notification()
    
    def send_payment_approved_notification(self):
        """
        Envía notificación al cliente cuando su pago es aprobado
        """
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = f'Pago Aprobado - Reserva #{self.booking.id}'
        message = f"""
        Hola {self.booking.customer.get_full_name() or self.booking.customer.username},
        
        ¡Excelentes noticias! Tu pago ha sido validado y aprobado.
        
        DETALLES DE TU RESERVA:
        - Número de Reserva: #{self.booking.id}
        - Servicio: {self.booking.get_services_display()}
        - Monto Pagado: ${self.amount}
        - Fecha Programada: {self.booking.scheduled_time.strftime('%d/%m/%Y %H:%M')}
        
        Tu reserva está confirmada. El proveedor se pondrá en contacto contigo próximamente.
        
        ¡Gracias por confiar en Liberi!
        
        ---
        El Equipo de Liberi
        """
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.booking.customer.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error enviando notificación de pago aprobado: {e}")
