from django.db import models
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils.text import slugify
from .custom_fields import SmartImageField, SmartFileField
from .validators import validate_image_size_5mb, validate_ecuador_phone

import secrets
import uuid

SERVICE_MODE_CHOICES = [
    ('home', 'Solo a domicilio'),
    ('local', 'Solo en local'),
    ('both', 'En local y a domicilio'),
]

# Extender el User de Django con un Profile
class Profile(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Cliente'),
        ('provider', 'Proveedor'),
        ('admin', 'Administrador'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='Usuario')
    phone = models.CharField(
        'Teléfono Celular', 
        max_length=13, 
        unique=True,
        null=True,
        blank=True,
        validators=[validate_ecuador_phone],
        error_messages={
            'unique': 'Ya existe una cuenta registrada con este número de teléfono.'
        },
        help_text='Número celular de Ecuador (09XXXXXXXX)'
    )
    role = models.CharField('Rol', max_length=10, choices=ROLE_CHOICES, default='customer')
    verified = models.BooleanField('Verificado', default=False)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    current_city = models.ForeignKey(
        'City',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Ciudad Actual',
        related_name='users_current',
        help_text='La ciudad donde el usuario está buscando servicios'
    )

    class Meta:
        db_table = 'profiles'
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def has_accepted_legal_documents(self):
        """Verifica si ha aceptado documentos legales según su rol"""
        from apps.legal.models import LegalDocument, LegalAcceptance
        
        if self.role == 'provider':
            required_docs = ['terms_provider', 'privacy_provider']
        else:
            required_docs = ['terms_user', 'privacy_user']
        
        for doc_type in required_docs:
            try:
                document = LegalDocument.objects.get(
                    document_type=doc_type,
                    is_active=True,
                    status='published'
                )
                
                if not LegalAcceptance.objects.filter(
                    user=self.user,
                    document=document
                ).exists():
                    return False
                    
            except LegalDocument.DoesNotExist:
                continue
        
        return True
    
# ============================================
# MODELO: City (NUEVO - Agregar ANTES de Zone)
# ============================================

class City(models.Model):
    """Ciudades disponibles en la plataforma"""
    name = models.CharField('Nombre', max_length=100, unique=True)
    code = models.CharField('Código', max_length=10, unique=True, help_text='Ej: QTO, GYE, CUI')
    country = models.CharField('País', max_length=100, default='Ecuador')
    active = models.BooleanField('Activa', default=True)
    display_order = models.IntegerField('Orden de visualización', default=0)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'cities'
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

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
        ('created', 'Creado'),
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('resubmitted', 'Re-enviado'),
    ]

    slug = models.SlugField(
        'Slug',
        unique=True,
        blank=True,
        help_text='URL amigable del perfil'
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, 
                                related_name='provider_profile', verbose_name='Usuario')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, 
                                 verbose_name='Categoría')
    description = models.TextField('Descripción')
    
    # NUEVOS CAMPOS - CAMBIO #8
    business_name = models.CharField('Nombre Comercial', max_length=200, blank=True,
                                     help_text='Nombre con el que se promociona el negocio')
    profile_photo = SmartImageField('Foto de Perfil', upload_to='profiles/', blank=True,
                                      help_text='Foto de perfil (puede ser comercial)', max_length=255, 
                                      validators=[validate_image_size_5mb])

    service_mode = models.CharField(
        'Modalidad de atención',
        max_length=10,
        choices=SERVICE_MODE_CHOICES,
        default='home',
        help_text='¿Atiende en domicilio, local, o ambos?'
    )
    # FIN NUEVOS CAMPOS
    
    coverage_zones = models.ManyToManyField('Zone', verbose_name='Zonas de cobertura',
                                           related_name='providers', blank=True)
    avg_travel_cost = models.DecimalField('Costo promedio de traslado', max_digits=6, 
                                          decimal_places=2, default=0)
    availability = models.JSONField('Disponibilidad', default=dict)
    # VERIFICATION FIELDS
    status = models.CharField('Estado', max_length=20, choices=STATUS_CHOICES, default='created')
    
    rejection_reasons = models.TextField(
        null=True, 
        blank=True,
        help_text='JSON con motivos de rechazo'
    )
    
    rejected_at = models.DateTimeField(null=True, blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    verification_attempts = models.PositiveIntegerField(default=0)
    
    # Datos extraídos de documentos
    extracted_id_name = models.CharField(max_length=200, null=True, blank=True)
    extracted_id_number = models.CharField(max_length=20, null=True, blank=True)
    extracted_id_expiry = models.DateField(null=True, blank=True)
    facial_match_score = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField('Activo', default=True)
    signed_contract_url = models.URLField('URL del contrato firmado', blank=True)
    id_card_front = SmartImageField('Cédula frontal', upload_to='documents/', 
                                    blank=True, max_length=255,
                                    validators=[validate_image_size_5mb])
    id_card_back = SmartImageField('Cédula posterior', upload_to='documents/', blank=True, max_length=255,
                                   validators=[validate_image_size_5mb])
    selfie_with_id = SmartImageField(
        'Foto Rostro con Cédula',
        upload_to='providers/validation/selfie/',
        blank=True,
        null=True,
        max_length=255,
        validators=[validate_image_size_5mb],
        help_text='Foto del rostro sosteniendo la cédula de identidad'
    )
    documents_verified = models.BooleanField(
        'Documentos Verificados',
        default=False,
        help_text='Indica si los documentos han sido validados por admin'
    )
    documents_verified_at = models.DateTimeField(
        'Documentos Verificados En',
        blank=True,
        null=True
    )
    registration_step = models.IntegerField(
        'Paso de Registro',
        default=1,
        help_text='1: Datos básicos, 2: Verificación identidad, 3: Completo'
    )
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'provider_profiles'
        verbose_name = 'Perfil de Proveedor'
        verbose_name_plural = 'Perfiles de Proveedores'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.business_name or self.user.get_full_name())
            self.slug = base_slug
            
            counter = 1
            original_slug = self.slug
            while ProviderProfile.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.business_name if self.business_name else self.user.get_full_name()
        return f"{display_name} - {self.category}"
    
    def get_display_name(self):
        """Retorna el nombre comercial si existe, sino el nombre completo del usuario"""
        return self.business_name if self.business_name else self.user.get_full_name()
    
    def get_full_display(self):
        """Retorna nombre comercial + nombre real entre paréntesis"""
        if self.business_name:
            return f"{self.business_name} ({self.user.get_full_name()})"
        return self.user.get_full_name()

    def can_publish_services(self):
        """Determina si el proveedor puede publicar servicios según modalidad."""
        
        # Para solo en local: debe tener al menos un local verificado
        if self.service_mode == 'local':
            return ProviderLocation.objects.filter(
                provider=self.user, 
                location_type='local', 
                is_verified=True
            ).exists()
        
        # Para solo a domicilio: debe tener ubicación base
        if self.service_mode == 'home':
            has_base = ProviderLocation.objects.filter(
                provider=self.user, 
                location_type='base'
            ).exists()
            return has_base
        
        # Para ambos: debe tener base O local verificado
        if self.service_mode == 'both':
            has_base = ProviderLocation.objects.filter(
                provider=self.user, 
                location_type='base'
            ).exists()
            has_local = ProviderLocation.objects.filter(
                provider=self.user, 
                location_type='local', 
                is_verified=True
            ).exists()
            return has_base or has_local
        
        return False
    
    def get_service_locations_by_zone(self, zone, location_type=None):
        """Retorna ubicaciones del proveedor en una zona específica."""
        qs = ProviderLocation.objects.filter(provider=self.user, zone=zone)
        
        if location_type:
            qs = qs.filter(location_type=location_type)
        
        if location_type == 'local':
            qs = qs.filter(is_verified=True)
        
        return qs

# ============================================
# NUEVO MODELO - AGREGAR DESPUÉS DE ProviderProfile
# ============================================

class ProviderLocation(models.Model):
    """Ubicaciones del proveedor: domicilio base o locales."""
    
    LOCATION_TYPE_CHOICES = [
        ('base', 'Domicilio base del proveedor'),
        ('local', 'Local / Sucursal del proveedor'),
    ]

    provider = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='provider_locations',
        verbose_name='Proveedor'
    )
    location_type = models.CharField(
        'Tipo de ubicación', 
        max_length=10, 
        choices=LOCATION_TYPE_CHOICES
    )
    city = models.ForeignKey(
        'City', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Ciudad'
    )
    zone = models.ForeignKey(
        'Zone', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Zona'
    )
    label = models.CharField(
        'Nombre de la ubicación', 
        max_length=100,
        help_text='Ej: Domicilio, Sucursal Norte, Oficina Centro'
    )
    address = models.TextField('Dirección completa')
    reference = models.CharField(
        'Referencia adicional', 
        max_length=255, 
        blank=True,
        help_text='Ej: Frente a farmacia, Pasaje interno'
    )
    latitude = models.DecimalField(
        'Latitud', 
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    longitude = models.DecimalField(
        'Longitud', 
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    whatsapp_number = models.CharField(
        'Número de WhatsApp para esta ubicación', 
        max_length=13, 
        blank=True,
        validators=[validate_ecuador_phone],
        help_text='Opcional: número específico para notificaciones'
    )
    document_proof = SmartImageField(
        'Comprobante de servicios básicos', 
        upload_to='provider_locations/docs/', 
        null=True, 
        blank=True,
        validators=[validate_image_size_5mb],
        help_text='Para locales: foto de pago de servicio básico'
    )
    is_verified = models.BooleanField(
        'Verificada por admin', 
        default=False,
        help_text='Solo locales verificados pueden recibir bookings'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'provider_locations'
        verbose_name = 'Ubicación de proveedor'
        verbose_name_plural = 'Ubicaciones de proveedores'
        indexes = [models.Index(fields=['provider', 'city', 'location_type'])]
        ordering = ['location_type', 'label']

    def __str__(self):
        return f"{self.provider.username} - {self.label}"

    def clean(self):
        """Validaciones a nivel de modelo"""
        super().clean()
        
        # ✅ VERIFICAR SI PROVIDER EXISTE ANTES DE USARLO
        if not self.provider_id:
            # Si no hay provider asignado, saltamos las validaciones
            # (El formulario ya se encarga de esto)
            return
        
        # Validar límite de locales por ciudad
        if self.location_type == 'local' and self.city:
            max_per_city = int(SystemConfig.get_config('max_provider_locations_per_city', 3))
            qs = ProviderLocation.objects.filter(
                provider=self.provider,
                city=self.city,
                location_type='local'
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= max_per_city:
                raise ValidationError(f'Límite de {max_per_city} locales por ciudad alcanzado')
        
        # Validar que solo haya un domicilio base
        if self.location_type == 'base':
            qs = ProviderLocation.objects.filter(
                provider=self.provider,
                location_type='base'
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError('Solo puede tener un domicilio base')

    def save(self, *args, **kwargs):
        if self.location_type == 'base':
            self.is_verified = True
        super().save(*args, **kwargs)


class Service(models.Model):
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='services',
                                verbose_name='Proveedor')
    service_code = models.UUIDField(
        'Código de Servicio',
        default=uuid.uuid4, 
        editable=False, 
        unique=True,
        help_text='Identificador único del servicio'
    )
    name = models.CharField('Nombre', max_length=200)
    description = models.TextField('Descripción', help_text='Puede incluir formato HTML básico')
    base_price = models.DecimalField('Precio base', max_digits=8, decimal_places=2)
    duration_minutes = models.IntegerField('Duración (minutos)')
    available = models.BooleanField('Disponible', default=True)
    
    # Múltiples imágenes del servicio (hasta 3)
    image_1 = SmartImageField('Imagen 1', upload_to='services/', blank=True, null=True, max_length=255,
                              validators=[validate_image_size_5mb])
    image_2 = SmartImageField('Imagen 2', upload_to='services/', blank=True, null=True, max_length=255,
                              validators=[validate_image_size_5mb])
    image_3 = SmartImageField('Imagen 3', upload_to='services/', blank=True, null=True, max_length=255,
                              validators=[validate_image_size_5mb])
    
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        db_table = 'services'
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - ${self.base_price}"
    
    def get_service_images(self):
        """Retorna lista de imágenes no nulas del servicio"""
        images = []
        for field_name in ['image_1', 'image_2', 'image_3']:
            image = getattr(self, field_name)
            if image:
                images.append(image)
        return images
    
    @property
    def primary_image(self):
        """Retorna la primera imagen disponible o None"""
        return self.image_1 if self.image_1 else (self.image_2 if self.image_2 else self.image_3)



class Location(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations',
                                verbose_name='Cliente')
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True,
                            verbose_name='Zona')
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Ciudad',
        related_name='locations'
    )
    address = models.TextField('Dirección')
    reference = models.CharField('Referencia', max_length=255, blank=True)
    label = models.CharField('Etiqueta', max_length=50, default='casa')
    
    # NUEVO CAMPO
    recipient_name = models.CharField(
        'Quién recibe el servicio',
        max_length=200,
        blank=True,
        help_text='Nombre de la persona que recibirá el servicio en esta ubicación'
    )
    
    latitude = models.DecimalField('Latitud', max_digits=9, decimal_places=6)
    longitude = models.DecimalField('Longitud', max_digits=9, decimal_places=6)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'locations'
        verbose_name = 'Ubicación'
        verbose_name_plural = 'Ubicaciones'

    def __str__(self):
        city_name = self.city.name if self.city else 'Sin ciudad'
        recipient_info = f" - {self.recipient_name}" if self.recipient_name else ""
        return f"{self.customer.username} - {self.label} ({city_name}){recipient_info}"
    
    def save(self, *args, **kwargs):
        # Auto-setear city desde zone si existe
        if self.zone and not self.city:
            self.city = self.zone.city
        super().save(*args, **kwargs)


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptado'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('dispute', 'Disputa'),
    ]
    ProviderProfile
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('pending_validation', 'Pendiente de Validación'),
        ('paid', 'Pagado'),
        ('refunded', 'Reembolsado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(
        'ID Corto (Slug)',
        db_index=True,
        max_length=12,
        blank=True,
        help_text='Identificador único corto para la reserva'
    )
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_bookings',
                                verbose_name='Cliente')
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_bookings',
                                verbose_name='Proveedor')
    provider_location = models.ForeignKey(
        'ProviderLocation', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        verbose_name='Ubicación del proveedor',
        help_text='Dónde se realizará el servicio',
        related_name='bookings'
    )
    service_list = models.JSONField('Lista de servicios', default=list)
    sub_total_cost = models.DecimalField('Subtotal', max_digits=10, decimal_places=2, default=0.0)
    total_cost = models.DecimalField('Costo total', max_digits=10, decimal_places=2)
    tax = models.DecimalField('Impuesto / IVA', max_digits=10, decimal_places=2, default=0.0)
    service = models.DecimalField('Costo del servicio', max_digits=10, decimal_places=2, default=0.0)
    travel_cost = models.DecimalField('Costo de movilizacion', max_digits=10, decimal_places=2, default=0.0)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True,
                                verbose_name='Ubicación')
    status = models.CharField('Estado', max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField('Estado de pago', max_length=20, 
                                     choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField('Método de pago', max_length=50, blank=True)
    provider_completed_at = models.DateTimeField(
        'Completado por Proveedor',
        null=True,
        blank=True,
        help_text='Timestamp cuando el proveedor marca como completado'
    )
    customer_completed_at = models.DateTimeField(
        'Completado por Cliente',
        null=True,
        blank=True,
        help_text='Timestamp cuando el cliente marca como completado'
    )
    scheduled_time = models.DateTimeField('Hora programada')
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)
    completion_code = models.CharField(
        'Código de Finalización',
        max_length=6,
        blank=True,
        null=True,
        help_text='Código de 6 dígitos que el cliente entrega al proveedor'
    )
    incident_reported = models.BooleanField(
        'Incidencia Reportada',
        default=False,
        help_text='Si el cliente reportó que no recibió el servicio'
    )
    incident_description = models.TextField(
        'Descripción de Incidencia',
        blank=True,
        null=True,
        help_text='Detalles del problema reportado por el cliente'
    )
    incident_reported_at = models.DateTimeField(
        'Incidencia Reportada En',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'bookings'
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Generar slug si no existe
        if not self.slug:
            # Usar primeros 8 caracteres del UUID
            base_slug = str(self.id)[:8].lower()
            self.slug = base_slug
            
            # Verificar que sea único
            counter = 1
            original_slug = self.slug
            while Booking.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)

    def get_services_display(self):
        """
        Retorna una representación legible de los servicios
        """
        if isinstance(self.service_list, list):
            return ', '.join([s.get('name', '') for s in self.service_list])
        return 'N/A'

    def __str__(self):
        return f"Reserva {self.booking_id} - {self.get_status_display()}"

    @property
    def booking_id(self):
        return self.slug if self.slug else  str(self.id)[:8].lower()

    @property
    def is_past(self):
        """Verifica si la reserva ya pasó"""
        return self.scheduled_time < timezone.now()
    
    @property
    def days_until(self):
        """Calcula días hasta la cita"""
        if self.is_past:
            return 0
        delta = self.scheduled_time - timezone.now()
        return delta.days
    
    @property
    def hours_until(self):
        """Calcula horas hasta la cita"""
        if self.is_past:
            return 0
        delta = self.scheduled_time - timezone.now()
        return int(delta.total_seconds() / 3600)

    def generate_completion_code(self):
        """Genera un código de 6 dígitos para completar el servicio"""
        import random
        self.completion_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.save(update_fields=['completion_code'])
        return self.completion_code
    
    def verify_completion_code(self, code):
        """Verifica si el código ingresado es correcto"""
        return self.completion_code == code
    
    def should_show_completion_code(self):
        """Determina si debe mostrar el código al cliente"""
        # Mostrar cuando: está aceptada, pagada, y faltan 2 horas o menos
        if self.status != 'accepted' or self.payment_status != 'paid':
            return False
        
        from django.utils import timezone
        now = timezone.now()
        time_until = self.scheduled_time - now
        hours_until = time_until.total_seconds() / 3600
        
        return hours_until <= 2

    def get_service_location_display(self):
        """Retorna display de dónde se realizará el servicio"""
        if self.provider_location:
            if self.provider_location.location_type == 'base':
                return f"A domicilio: {self.provider_location.address}"
            else:
                return f"En local: {self.provider_location.label} - {self.provider_location.address}"
        return "Sin ubicación especificada"

    def get_notification_whatsapp(self):
        """Retorna el número de WhatsApp para notificaciones."""
        if self.provider_location and self.provider_location.whatsapp_number:
            return self.provider_location.whatsapp_number
        
        if hasattr(self.provider, 'profile') and self.provider.profile.phone:
            return self.provider.profile.phone
        
        return None


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
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        verbose_name='Ciudad',
        related_name='zones'
    )
    active = models.BooleanField('Activa', default=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        db_table = 'zones'
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'
        ordering = ['city__name', 'name']
        unique_together = ['name', 'city'] 

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
        'Booking',
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
    proof_image = SmartImageField(
        upload_to='payment_proofs/',
        blank=True,
        null=True,
        verbose_name='Comprobante de Pago',
        help_text='Imagen o foto del comprobante de pago',
        max_length=256,
        validators=[validate_image_size_5mb]
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
        'Booking',
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
    transfer_receipt = SmartFileField(
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
        Crea notificaciones para cliente y proveedor
        """
        self.status = 'completed'
        self.validated_by = validated_by
        self.validated_at = timezone.now()
        self.save()
        
        # Actualizar el estado de pago de la reserva
        self.booking.payment_status = 'paid'
        self.booking.save()
        
        # Crear notificaciones en pantalla y enviar emails
        self.send_payment_approved_notifications()
    
    def send_payment_approved_notifications(self):
        """
        Crea notificaciones en la base de datos y envía emails tanto al cliente como al proveedor
        """
        from django.conf import settings
        
        # ============================================
        # NOTIFICACIÓN PARA EL CLIENTE
        # ============================================
        
        # Crear notificación en base de datos para el cliente
        Notification.objects.create(
            user=self.booking.customer,
            notification_type='payment_verified',
            title='✅ Pago Verificado',
            message=f'Tu pago de ${self.amount} para la reserva ha sido verificado y confirmado. Tu reserva está activa.',
            booking=self.booking,
            action_url=f'/bookings/{self.booking.id}/'
        )

        # Enviar email de forma asincrónica
        try:
            from core.tasks import send_payment_approved_to_customer_task
            send_payment_approved_to_customer_task.delay(payment_id=self.id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando email al cliente: {e}")
        
        # ============================================
        # NOTIFICACIÓN PARA EL PROVEEDOR
        # ============================================
        
        # Crear notificación en base de datos para el proveedor
        Notification.objects.create(
            user=self.booking.provider,
            notification_type='payment_verified',
            title='💰 Pago Confirmado',
            message=f'El pago de {self.booking.customer.get_full_name() or self.booking.customer.username} por ${self.amount} ha sido verificado. Reserva confirmada.',
            booking=self.booking,
            action_url=f'/bookings/{self.booking.id}/'
        )

        # Enviar email de forma asincrónica
        try:
            from core.tasks import send_payment_approved_to_provider_task
            send_payment_approved_to_provider_task.delay(payment_id=self.id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando email al proveedor: {e}")

# ============================================
# MODELO: Bank
# ============================================
class Bank(models.Model):
    """Bancos disponibles en el sistema"""
    name = models.CharField('Nombre', max_length=128, unique=True)
    code = models.CharField('Código', max_length=10, unique=True)
    country = models.CharField('País', max_length=64, default='EC')
    is_active = models.BooleanField('Activo', default=True)
    created_at = models.DateTimeField('Creado', auto_now_add=True)

    class Meta:
        db_table = 'banks'
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'
        ordering = ['name']

    def __str__(self):
        return self.name

class ProviderBankAccount(models.Model):
    """Cuenta bancaria del proveedor para recibir retiros"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_bank_accounts', verbose_name='Proveedor')
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, verbose_name='Banco')  # CAMBIADO
    account_type = models.CharField('Tipo de Cuenta', max_length=64, choices=[('checking','Cuenta Corriente'),('savings','Cuenta de Ahorros')])
    country = models.CharField('País', max_length=64, default='EC')
    account_number_masked = models.CharField('Número Enmascarado', max_length=64)
    account_number_encrypted = models.TextField('Número Cifrado', null=True, blank=True)
    owner_fullname = models.CharField('Titular', max_length=200)
    is_primary = models.BooleanField('Principal', default=False)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)

    class Meta:
        db_table = 'provider_bank_accounts'
        verbose_name = 'Cuenta Bancaria del Proveedor'
        verbose_name_plural = 'Cuentas Bancarias de Proveedores'
        unique_together = (('provider', 'account_number_masked'),)

    def __str__(self):
        return f"{self.bank.name} - {self.account_number_masked}"


class WithdrawalRequest(models.Model):
    """Solicitud de retiro del proveedor"""
    STATUS_CHOICES = (('pending','Pendiente'), ('rejected','Rechazado'), ('completed','Completado'))
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_requests', verbose_name='Proveedor')
    provider_bank_account = models.ForeignKey(ProviderBankAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Cuenta Bancaria')
    requested_amount = models.DecimalField('Monto Solicitado', max_digits=10, decimal_places=2)
    commission_percent = models.DecimalField('% Comisión', max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField('Monto Comisión', max_digits=10, decimal_places=2)
    amount_payable = models.DecimalField('Monto a Pagar', max_digits=10, decimal_places=2)
    description = models.TextField('Descripción', blank=True)
    status = models.CharField('Estado', max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField('Nota Admin', blank=True)
    transfer_receipt_number = models.CharField('Nº Comprobante', max_length=256, blank=True)
    covered_bookings = models.JSONField('Reservas Cubiertas', default=list, blank=True)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)
    processed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='processed_withdrawals', verbose_name='Procesado Por')

    class Meta:
        db_table = 'withdrawal_requests'
        verbose_name = 'Solicitud de Retiro'
        verbose_name_plural = 'Solicitudes de Retiro'
        ordering = ['-created_at']

    def __str__(self):
        return f"Retiro {str(self.id)[:8]} - ${self.requested_amount}"
    
class EmailVerificationToken(models.Model):
    """Token para verificar email de usuarios nuevos"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification_token')
    email = models.EmailField('Email a Verificar')
    token = models.CharField('Token', max_length=255, unique=True)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    verified_at = models.DateTimeField('Verificado en', null=True, blank=True)
    is_verified = models.BooleanField('Verificado', default=False)
    
    class Meta:
        db_table = 'email_verification_tokens'
        verbose_name = 'Token de Verificación de Email'
        verbose_name_plural = 'Tokens de Verificación de Email'
    
    def __str__(self):
        return f"Token para {self.user.username} - {self.email}"
    
    @classmethod
    def create_for_user(cls, user, email):
        cls.objects.filter(user=user).delete()
        token = secrets.token_urlsafe(32)
        verification_token = cls.objects.create(
            user=user,
            email=email,
            token=token,
            is_verified=False
        )
        return verification_token
    
    def is_valid(self):
        if self.is_verified:
            return False
        expiry_time = self.created_at + timedelta(hours=24)
        return timezone.now() < expiry_time
    
    def verify(self):
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save()
    
    def delete_if_expired(self):
        if not self.is_valid():
            self.delete()
            return True
        return False

class PasswordResetToken(models.Model):
    """Token para resetear contraseña"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token = models.CharField('Token', max_length=255, unique=True)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    used_at = models.DateTimeField('Usado en', null=True, blank=True)
    is_used = models.BooleanField('Usado', default=False)
    
    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = 'Token de Reset de Contraseña'
        verbose_name_plural = 'Tokens de Reset de Contraseña'
    
    def __str__(self):
        return f"Reset token para {self.user.username}"
    
    @classmethod
    def create_for_user(cls, user):
        """Crea un nuevo token para reset de contraseña"""
        cls.objects.filter(user=user).delete()
        token = secrets.token_urlsafe(32)
        reset_token = cls.objects.create(
            user=user,
            token=token,
            is_used=False
        )
        return reset_token
    
    def is_valid(self):
        """Verifica si el token es válido (no expirado ni usado)"""
        if self.is_used:
            return False
        expiry_time = self.created_at + timedelta(hours=1)
        return timezone.now() < expiry_time
    
    def mark_as_used(self):
        """Marca el token como usado"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    def delete_if_expired(self):
        """Elimina el token si está expirado"""
        if not self.is_valid() and not self.is_used:
            self.delete()
            return True
        return False