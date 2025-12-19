"""
Test cases for error sanitization
"""
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from apps.core.error_sanitizer import (
    sanitize_error,
    sanitize_database_integrity_error,
    sanitize_validation_error,
    remove_sensitive_data
)


class ErrorSanitizerTestCase(TestCase):
    """Test error message sanitization"""
    
    def test_sanitize_phone_duplicate_error(self):
        """Test that phone duplicate errors are sanitized"""
        # Simulate a real IntegrityError from PostgreSQL
        error = IntegrityError(
            'duplicate key value violates unique constraint "profiles_phone_d8af2ef4_uniq" '
            'DETAIL: Key (phone)=(0998981433) already exists.'
        )
        
        result = sanitize_database_integrity_error(error)
        
        # Should return user-friendly message
        self.assertIn("teléfono", result.lower())
        self.assertIn("registrado", result.lower())
        
        # Should NOT contain sensitive data
        self.assertNotIn("0998981433", result)
        self.assertNotIn("profiles_phone", result)
        self.assertNotIn("constraint", result)
        self.assertNotIn("DETAIL", result)
    
    def test_sanitize_email_duplicate_error(self):
        """Test that email duplicate errors are sanitized"""
        error = IntegrityError(
            'duplicate key value violates unique constraint "users_email_uniq" '
            'DETAIL: Key (email)=(test@example.com) already exists.'
        )
        
        result = sanitize_database_integrity_error(error)
        
        self.assertIn("email", result.lower())
        self.assertIn("registrado", result.lower())
        self.assertNotIn("test@example.com", result)
        self.assertNotIn("users_email", result)
    
    def test_sanitize_username_duplicate_error(self):
        """Test that username duplicate errors are sanitized"""
        error = IntegrityError(
            'duplicate key value violates unique constraint "users_username_key" '
            'DETAIL: Key (username)=(johndoe) already exists.'
        )
        
        result = sanitize_database_integrity_error(error)
        
        self.assertIn("usuario", result.lower())
        self.assertNotIn("johndoe", result)
        self.assertNotIn("users_username", result)
    
    def test_sanitize_foreign_key_error(self):
        """Test foreign key constraint errors"""
        error = IntegrityError(
            'insert or update on table "bookings" violates foreign key constraint "fk_service" '
            'DETAIL: Key (service_id)=(999) is not present in table "services".'
        )
        
        result = sanitize_database_integrity_error(error)
        
        self.assertIn("integridad", result.lower())
        self.assertNotIn("bookings", result)
        self.assertNotIn("fk_service", result)
        self.assertNotIn("999", result)
    
    def test_remove_sensitive_patterns(self):
        """Test that sensitive patterns are removed from messages"""
        message = "Error with phone 0998981433 and email test@example.com in table profiles_phone_d8af2ef4_uniq"
        
        result = remove_sensitive_data(message)
        
        # Should remove phone, email, and constraint names
        self.assertNotIn("0998981433", result)
        self.assertNotIn("test@example.com", result)
        self.assertNotIn("profiles_phone_d8af2ef4_uniq", result)
        self.assertIn("[datos ocultos]", result)
    
    def test_debug_mode_shows_technical_details(self):
        """Test that debug mode returns technical details"""
        error = IntegrityError("duplicate key constraint violation")
        
        result = sanitize_error(error, debug_mode=True)
        
        # In debug mode, should show the actual error
        self.assertIn("duplicate key", result)
    
    def test_production_mode_hides_details(self):
        """Test that production mode hides technical details"""
        error = IntegrityError(
            'duplicate key value violates unique constraint "profiles_phone_d8af2ef4_uniq"'
        )
        
        result = sanitize_error(error, debug_mode=False)
        
        # Should be user-friendly
        self.assertNotIn("constraint", result)
        self.assertNotIn("profiles_phone", result)
        
    def test_validation_error_sanitization(self):
        """Test ValidationError sanitization preserves field messages"""
        error = ValidationError({
            'phone': ['Este campo es requerido'],
            'email': ['Formato de email inválido']
        })
        
        result = sanitize_validation_error(error)
        
        # Should preserve useful validation messages
        self.assertIn("Phone", result)
        self.assertIn("requerido", result)
        self.assertIn("Email", result)
        self.assertIn("inválido", result)
    
    def test_generic_error_fallback(self):
        """Test generic error returns safe fallback message"""
        error = Exception("Some internal server error with sensitive data")
        
        result = sanitize_error(error, debug_mode=False)
        
        # Should return generic safe message
        self.assertIn("error", result.lower())
        # Should not contain the actual exception message in prod
        self.assertNotIn("internal server error", result)


class ErrorSanitizerIntegrationTestCase(TestCase):
    """Integration tests with actual Django models"""
    
    def test_duplicate_phone_registration(self):
        """Test that duplicate phone registration shows sanitized error"""
        from django.contrib.auth.models import User
        from apps.core.models import Profile
        
        # Create first user
        user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        Profile.objects.create(
            user=user1,
            phone='0998981433',
            role='customer'
        )
        
        # Try to create second user with same phone
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        try:
            Profile.objects.create(
                user=user2,
                phone='0998981433',  # Duplicate!
                role='customer'
            )
            self.fail("Should have raised IntegrityError")
        except IntegrityError as e:
            # Sanitize the error
            safe_message = sanitize_error(e, debug_mode=False)
            
            # Verify it's user-friendly
            self.assertIn("teléfono", safe_message.lower())
            self.assertNotIn("0998981433", safe_message)
            self.assertNotIn("constraint", safe_message)
