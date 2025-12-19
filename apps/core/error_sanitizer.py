"""
Error Sanitization Utility

This module provides functions to sanitize exception messages before displaying
them to users, preventing exposure of:
- Database structure (table names, constraints, SQL)
- Personal data (phone numbers, emails, IDs)
- Technology stack details
- System internals

All technical details are logged server-side for debugging.
"""

import re
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


# Patterns to detect and remove sensitive information
SENSITIVE_PATTERNS = [
    # Database constraint names
    r'[a-z_]+_[a-z0-9]+_[a-z0-9]+',  # e.g., profiles_phone_d8af2ef4_uniq
    # SQL keywords and details
    r'DETAIL:.*',
    r'KEY.*',
    r'CONSTRAINT.*',
    r'violates.*constraint',
    # Phone numbers (Ecuador format)
    r'\b0\d{9}\b',
    r'\(\d{3}\)\s*\d{3}-\d{4}',
    # Email addresses
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    # Database/table references
    r'relation\s+"[^"]+"',
    r'table\s+"[^"]+"',
]


def sanitize_error(exception, debug_mode=None, context=None):
    """
    Main entry point for error sanitization.
    
    Args:
        exception: The exception to sanitize
        debug_mode: If True, return technical details. Defaults to settings.DEBUG
        context: Optional dict with request context for logging
    
    Returns:
        str: User-friendly error message
    """
    if debug_mode is None:
        debug_mode = getattr(settings, 'DEBUG', False)
    
    # Log the full technical error server-side
    log_detailed_error(exception, context)
    
    # In debug mode, return technical details
    if debug_mode:
        return str(exception)
    
    # Sanitize based on exception type
    if isinstance(exception, IntegrityError):
        return sanitize_database_integrity_error(exception)
    elif isinstance(exception, DatabaseError):
        return sanitize_database_error(exception)
    elif isinstance(exception, ValidationError):
        return sanitize_validation_error(exception)
    else:
        return sanitize_generic_error(exception)


def sanitize_database_integrity_error(exception):
    """
    Sanitize IntegrityError exceptions (unique constraints, foreign keys, etc.)
    
    Returns user-friendly messages based on the type of constraint violation.
    """
    error_str = str(exception).lower()
    
    # Duplicate key violations
    if 'unique' in error_str or 'duplicate' in error_str:
        # Check what field is duplicated
        if 'phone' in error_str or 'teléfono' in error_str or 'telefono' in error_str:
            return "Este teléfono ya está registrado en el sistema."
        elif 'email' in error_str or 'correo' in error_str:
            return "Este email ya está registrado en el sistema."
        elif 'username' in error_str or 'usuario' in error_str:
            return "Este nombre de usuario ya está en uso."
        else:
            return "Este registro ya existe en el sistema. Por favor verifica los datos ingresados."
    
    # Foreign key violations
    if 'foreign key' in error_str or 'fk_' in error_str:
        return "Error de integridad de datos. Por favor verifica que todos los campos sean válidos."
    
    # Check constraints
    if 'check constraint' in error_str or 'ck_' in error_str:
        return "Los datos ingresados no cumplen con las validaciones requeridas."
    
    # Generic integrity error
    return "Error al guardar los datos. Por favor verifica la información ingresada."


def sanitize_database_error(exception):
    """
    Sanitize generic database errors.
    """
    error_str = str(exception).lower()
    
    if 'connection' in error_str:
        return "Error de conexión con la base de datos. Por favor intenta nuevamente en unos momentos."
    
    if 'timeout' in error_str:
        return "La operación tardó demasiado. Por favor intenta nuevamente."
    
    return "Error temporal del sistema. Por favor intenta nuevamente."


def sanitize_validation_error(exception):
    """
    Sanitize Django ValidationError.
    
    Preserves useful field-level validation messages but removes technical details.
    """
    if hasattr(exception, 'message_dict'):
        # Field-specific errors
        messages = []
        for field, errors in exception.message_dict.items():
            field_name = field.replace('_', ' ').capitalize()
            for error in errors:
                # Remove sensitive patterns from validation messages
                clean_message = remove_sensitive_data(str(error))
                messages.append(f"{field_name}: {clean_message}")
        return " ".join(messages)
    
    elif hasattr(exception, 'messages'):
        # List of messages
        clean_messages = [remove_sensitive_data(str(msg)) for msg in exception.messages]
        return " ".join(clean_messages)
    
    else:
        # Single message
        return remove_sensitive_data(str(exception))


def sanitize_generic_error(exception):
    """
    Sanitize generic exceptions.
    
    Returns a safe, generic message while logging the actual error.
    """
    error_str = str(exception).lower()
    
    # File/upload errors
    if 'file' in error_str or 'upload' in error_str:
        return "Error al procesar el archivo. Por favor verifica el formato y tamaño."
    
    # Permission errors
    if 'permission' in error_str or 'denied' in error_str:
        return "No tienes permisos para realizar esta acción."
    
    # Value errors (often from data conversion)
    if isinstance(exception, ValueError):
        return "Formato de datos inválido. Por favor verifica la información ingresada."
    
    # Generic fallback
    return "Ha ocurrido un error inesperado. Por favor contacta al soporte técnico."


def remove_sensitive_data(message):
    """
    Remove sensitive patterns from error messages.
    
    Args:
        message: The error message to clean
    
    Returns:
        str: Message with sensitive data removed
    """
    clean_message = str(message)
    
    for pattern in SENSITIVE_PATTERNS:
        clean_message = re.sub(pattern, '[datos ocultos]', clean_message, flags=re.IGNORECASE)
    
    return clean_message


def log_detailed_error(exception, context=None):
    """
    Log the full technical error details server-side.
    
    Args:
        exception: The exception that occurred
        context: Optional dict with additional context (user, request, etc.)
    """
    extra_data = {
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
    }
    
    if context:
        extra_data.update(context)
    
    logger.error(
        f"Error occurred: {type(exception).__name__}",
        exc_info=True,
        extra=extra_data
    )


def get_sanitized_error_response(exception, request=None):
    """
    Get a complete sanitized error response for API/AJAX requests.
    
    Args:
        exception: The exception that occurred
        request: The Django request object (optional, for context)
    
    Returns:
        dict: Response data with sanitized error message
    """
    context = {}
    if request:
        context.update({
            'path': request.path,
            'method': request.method,
            'user_id': request.user.id if request.user.is_authenticated else None,
        })
    
    safe_message = sanitize_error(exception, context=context)
    
    return {
        'success': False,
        'error': safe_message,
    }
