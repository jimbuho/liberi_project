from rest_framework import serializers
from django.contrib.auth.models import User
from apps.core.models import Profile, City


class UserSerializer(serializers.ModelSerializer):
    """Serializer básico para Usuario"""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name']
        read_only_fields = ['id', 'email', 'username']


class CitySerializer(serializers.ModelSerializer):
    """Serializer para Ciudad"""
    
    class Meta:
        model = City
        fields = ['id', 'name', 'code']


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer para Perfil de Usuario"""
    current_city = CitySerializer(read_only=True)
    
    class Meta:
        model = Profile
        fields = ['phone', 'role', 'verified', 'current_city', 'created_at']
        read_only_fields = ['role', 'verified', 'created_at']


class RegisterSerializer(serializers.Serializer):
    """Serializer para registro de nuevo usuario"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(min_length=8, write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    phone = serializers.CharField(max_length=13, required=True)
    role = serializers.ChoiceField(choices=['customer', 'provider'], required=True)
    device_token = serializers.CharField(required=False, allow_blank=True)
    device_type = serializers.ChoiceField(choices=['ios', 'android'], required=False)
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este email")
        return value
    
    def validate_phone(self, value):
        # Validación básica de teléfono Ecuador
        import re
        if not re.match(r'^09\d{8}$', value):
            raise serializers.ValidationError(
                "Formato inválido. Debe ser un número de celular ecuatoriano (09XXXXXXXX)"
            )
        if Profile.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este número de teléfono")
        return value
    
    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Las contraseñas no coinciden"})
        return attrs


class LoginSerializer(serializers.Serializer):
    """Serializer para login"""
    username_or_email = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    device_token = serializers.CharField(required=False, allow_blank=True)
    device_type = serializers.ChoiceField(choices=['ios', 'android'], required=False)


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer para autenticación con Google"""
    id_token = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=['customer', 'provider'], required=False)
    device_token = serializers.CharField(required=False, allow_blank=True)
    device_type = serializers.ChoiceField(choices=['ios', 'android'], required=False)


class TokenResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de tokens JWT"""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    user = UserSerializer()
    profile = ProfileSerializer()
    is_new_user = serializers.BooleanField(required=False)
    requires_profile_completion = serializers.BooleanField(required=False)


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer para refresh token"""
    refresh_token = serializers.CharField(required=True)


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer para solicitar reset de contraseña"""
    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer para resetear contraseña con token"""
    token = serializers.CharField(required=True)
    password = serializers.CharField(min_length=8, write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Las contraseñas no coinciden"})
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    """Serializer para verificar email"""
    token = serializers.CharField(required=True)
