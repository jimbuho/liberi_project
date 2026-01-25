import os
import sys
import dj_database_url
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps directory to Python path
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

GOOGLE_TAG_MANAGER_ID = os.getenv('GOOGLE_TAG_MANAGER_ID', 'GTM-XXXXXXX')

# ============================================
# REFERRER-POLICY PARA PAYPHONE - CRÍTICO
# ============================================
SECURE_REFERRER_POLICY = 'origin-when-cross-origin'

CSRF_TRUSTED_ORIGINS = [
    "https://liberi-project.fly.dev",
    "https://liberi.app",
    "https://www.liberi.app",  # Si usas www
    "http://localhost:8000",
]

# ============================================
# CONTENT SECURITY POLICY - PAYPHONE COMPATIBLE
# ============================================
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ("'self'",),
    'script-src': (
        "'self'",
        "'unsafe-inline'",
        'https://cdn.payphonetodoesposible.com',
    ),
    'style-src': (
        "'self'",
        "'unsafe-inline'",
        'https://cdn.payphonetodoesposible.com',
    ),
    'connect-src': (
        "'self'",
        'https://cdn.payphonetodoesposible.com',
    ),
    'frame-src': ('https://cdn.payphonetodoesposible.com',),
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    
    # Custom apps (organized in apps/ directory)
    'apps.core',
    'apps.payments',
    'apps.messaging',
    'apps.frontend',
    'apps.legal',
    'apps.whatsapp_notifications',
    
    # New refactored apps
    'apps.authentication',
    'apps.profiles',
    'apps.bookings',
    'apps.public',

    # Celery y Beat
    'django_celery_beat',
    'django_celery_results',

    # One Signal Notifications
    'apps.push_notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'apps.legal.middleware.LegalAcceptanceMiddleware',
    'core.middleware.PayPhoneReferrerPolicyMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.EmailVerificationMiddleware',
    'core.middleware.ProviderProfileCheckMiddleware',
]

ROOT_URLCONF = 'liberi_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'liberi_project.wsgi.application'

ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')  # development, production

if ENVIRONMENT == 'production':
    # Configuración para Supabase (Producción)
    DATABASES = {
        "default": dj_database_url.parse(os.environ.get("DATABASE_URL"))    
    }

    # === SOLO ESTO PARA HTTPS EN FLY ===
    SECURE_PROXY_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # AGREGAR ESTAS LÍNEAS PARA FORZAR HTTPS EN OAUTH
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
    SOCIALACCOUNT_LOGIN_ON_GET = True
else:
    # Configuración para PostgreSQL local (Desarrollo)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('LOCAL_DB_NAME', 'liberi_db'),
            'USER': os.getenv('LOCAL_DB_USER', 'postgres'),
            'PASSWORD': os.getenv('LOCAL_DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('LOCAL_DB_HOST', 'localhost'),
            'PORT': os.getenv('LOCAL_DB_PORT', '5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

ADMINS = [
    ('Diego', os.getenv('ADMIN_EMAIL', 'liberiservices@gmail.com')),
]

MANAGERS = ADMINS

SERVER_EMAIL = 'liberiservices@gmail.com'
EMAIL_SUBJECT_PREFIX = '[Liberi Error] '

# ============================================
# ALLAUTH
# ============================================
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Configuración de allauth
ACCOUNT_LOGIN_METHODS = {'username', 'email'} 
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Ya manejamos verificación custom


ACCOUNT_SIGNUP_FIELDS = [
    'email*',      # * indica que es obligatorio
    'username*',   # * indica que es obligatorio
    'password1*',  # * indica que es obligatorio
    'password2*',  # * indica que es obligatorio
]

# Conectar cuentas existentes si el email coincide
SOCIALACCOUNT_ADAPTER = 'core.adapters.CustomSocialAccountAdapter'

# Configuración de Google OAuth
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', default=''),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET', default=''),
            'key': ''
        }
    }
}

# Signup
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# ============================================
# LOGGING
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'errors.log'),
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'core.adapters': {  # AGREGAR ESTO
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'core.error_sanitizer': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
        },
        'frontend.views': {  # AGREGAR ESTO
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'allauth': {  # AGREGAR ESTO
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

# Asegurar que existe el directorio de logs
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        'https://liberi.ec',
        'https://www.liberi.ec',
    ]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@liberi.ec')

PAYPHONE_API_TOKEN = os.getenv('PAYPHONE_API_TOKEN', '')
PAYPHONE_CLIENT_ID = os.getenv('PAYPHONE_CLIENT_ID', '')
PAYPHONE_CALLBACK_URL = os.getenv('PAYPHONE_CALLBACK_URL', '')
PAYPHONE_API_URL = os.getenv('PAYPHONE_API_URL', '')
PAYPHONE_STORE_ID = os.getenv('PAYPHONE_STORE_ID', '')
PAYPHONE_URL_CONFIRM_PAYPHONE = os.getenv('PAYPHONE_URL_CONFIRM_PAYPHONE', '')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8000')

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
ACCOUNT_SIGNUP_REDIRECT_URL = '/dashboard/' 
LOGOUT_REDIRECT_URL = '/'

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================================
# EMAIL CONFIGURATION - BREVO
# ============================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp-relay.brevo.com')
EMAIL_PORT = os.getenv('EMAIL_PORT', 587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  
DEFAULT_FROM_EMAIL =  os.getenv('DEFAULT_FROM_EMAIL', 'noreply@liberi.app')
EMAIL_VERIFICATION_EXPIRE_HOURS = 24

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')
SITE_URL = BASE_URL

# ============================================
# TAREAS SEGUNDO PLANO - CELERY
# ============================================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Guayaquil'
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos máximo
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutos soft limit

# ============================================
# TWILIO WHATSAPP CONFIGURATION
# ============================================
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+15557726158')
WHATSAPP_TEST_MODE = os.getenv('WHATSAPP_TEST_MODE', 'False') == 'True'

CELERY_BEAT_SCHEDULE = {
    'send-service-reminders': {
        'task': 'whatsapp_notifications.tasks.send_service_reminders',
        'schedule': 3600.0,  # cada 60 minutos
    },
    'check-uncompleted-services': {
        'task': 'core.tasks.check_uncompleted_services',
        'schedule': crontab(minute=0),  # Cada hora en punto
    },
    'send-push-reminders': {
        'task': 'push_notifications.tasks.send_push_reminders',
        'schedule': 3600.0,
    },
}

# Agregar al final
LIBERI_WITHDRAWAL_COMMISSION_PERCENT = float(os.getenv('LIBERI_WITHDRAWAL_COMMISSION_PERCENT', '10'))
LIBERI_WITHDRAWAL_WEEKLY_LIMIT = float(os.getenv('LIBERI_WITHDRAWAL_WEEKLY_LIMIT', '500.0'))
LIBERI_WITHDRAWAL_MAX_PER_DAY = int(os.getenv('LIBERI_WITHDRAWAL_MAX_PER_DAY', '1'))

TAXES_IVA = os.getenv('TAXES_IVA', 0.15)
TAXES_ENDUSER_SERVICE_COMMISSION = os.getenv('TAXES_SERVICE_COMMISSION', 1)

TWILIO_TEMPLATES = {
        'booking_created': {
            'content_sid': os.getenv('TWILIO_TEMPLATE_BOOKING_CREATE', ''),
            'friendly_name': 'booking_created',
            'variables_count': 3,  # nombre_cliente, servicio, fecha_hora
        },
        'booking_accepted': {
            'content_sid': os.getenv('TWILIO_TEMPLATE_BOOKING_ACEPTED', ''),
            'friendly_name': 'booking_accepted',
            'variables_count': 3,  # nombre_proveedor, servicio, booking_url
        },
        'payment_confirmed': {
            'content_sid': os.getenv('TWILIO_TEMPLATE_BOOKING_CONFIRMED', ''),
            'friendly_name': 'payment_confirmed',
            'variables_count': 2,  # nombre_cliente, servicio
        },
        'reminder': {
            'content_sid': os.getenv('TWILIO_TEMPLATE_BOOKING_REMINDER', ''),
            'friendly_name': 'reminder',
            'variables_count': 3,  # servicio, hora, booking_url
        },
    }

# ============================================
# PROVIDER VERIFICATION CONFIGURATION
# ============================================
PROVIDER_VERIFICATION_CONFIG = {
    # Umbrales de similitud
    'facial_match_threshold': 0.85,
    'semantic_similarity_threshold': 0.3,
    'category_match_threshold': 0.25,
    
    # Límites de re-verificación (varían según entorno)
    # Development: testing rápido, Production: más restrictivo
    'max_verification_attempts': 5 if ENVIRONMENT == 'development' else 3,
    'reverification_cooldown_hours': 1/60 if ENVIRONMENT == 'development' else 0.25,  # 1 min dev, 15 min prod
    
    # Longitudes de texto
    'min_description_length': 50,
    'max_description_length': 1000,
    
    # Moderación de contenido
    'nudity_threshold': 0.7,
    'violence_threshold': 0.7,
    'drugs_threshold': 0.6,
    
    # Timeouts
    'image_processing_timeout': 30,  # segundos
    'text_analysis_timeout': 10,  # segundos
}
# Category keywords for semantic matching
PROVIDER_VERIFICATION_CONFIG['category_keywords'] = {
    'Belleza': [
        # Servicios generales
        'belleza', 'estética', 'estetica', 'cosmetología', 'cosmetologia', 'salon', 'salón',
        # Cabello
        'cabello', 'pelo', 'corte', 'cortes', 'peinado', 'peinados', 'peluquería', 'peluqueria',
        'tintura', 'tinte', 'coloración', 'coloracion', 'mechas', 'alisado', 'permanente',
        'brushing', 'secado', 'lavado de cabello', 'tratamiento capilar',
        # Maquillaje
        'maquillaje', 'makeup', 'maquillar',
        # Uñas
        'uñas', 'unas', 'manicure', 'manicura', 'pedicure', 'pedicura', 'esmaltado',
        # Cejas y pestañas
        'cejas', 'pestañas', 'pestanas', 'microblading', 'laminado',
        # Tratamientos faciales
        'facial', 'faciales', 'limpieza facial', 'mascarilla', 'hidratación', 'hidratacion',
        # Depilación
        'depilación', 'depilacion', 'cera', 'láser', 'laser',
        # Tratamientos corporales
        'masaje', 'masajes', 'spa', 'relajación', 'relajacion',
        # Otros
        'tratamiento', 'tratamientos', 'cuidado personal', 'imagen personal',
    ],
    'Limpieza': [
        'hogar', 'casa', 'domicilio', 'oficina', 'local', 'comercio',
        'desinfección', 'desinfeccion', 'sanitización', 'sanitizacion',
        'lavado', 'lavar', 'planchado', 'planchar', 'organización', 'organizacion',
        'limpieza', 'limpiar', 'aseo', 'orden', 'ordenar',
        'aspirado', 'aspirar', 'trapeado', 'trapear', 'barrido', 'barrer',
        'ventanas', 'vidrios', 'pisos', 'alfombras', 'muebles',
        'cocina', 'baño', 'bano', 'habitaciones',
    ],
}

# Prohibited keywords for illegal content detection
PROVIDER_VERIFICATION_CONFIG['prohibited_keywords'] = {
    'lavado_activos': [
        'lavado de dinero', 'blanqueo',
    ],
    'armas': [
        'venta de armas', 'pistolas',
    ],
    'pornografia': [
        'servicios sexuales', 'contenido adulto',
    ],
}

ONESIGNAL_APP_ID = os.getenv('ONESIGNAL_APP_ID', '')
ONESIGNAL_REST_API_KEY = os.getenv('ONESIGNAL_REST_API_KEY', '')
PUSH_NOTIFICATIONS_ENABLED = os.getenv('PUSH_NOTIFICATIONS_ENABLED', 'True') == 'True'