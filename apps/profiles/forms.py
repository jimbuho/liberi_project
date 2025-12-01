from django import forms
from django.core.exceptions import ValidationError
from apps.core.models import ProviderLocation, ProviderProfile, SystemConfig

class ProviderProfileServiceModeForm(forms.ModelForm):
    """Formulario para seleccionar modalidad de atención"""
    
    class Meta:
        model = ProviderProfile
        fields = ['service_mode']
        widgets = {
            'service_mode': forms.RadioSelect(
                attrs={'class': 'form-check-input'}
            )
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_mode'].label = '¿Cómo quieres atender?'
        self.fields['service_mode'].help_text = 'Determinará qué ubicaciones registrar'


class ProviderLocationForm(forms.ModelForm):
    """Formulario para crear/editar ubicaciones"""
    
    class Meta:
        model = ProviderLocation
        fields = [
            'location_type', 'city', 'zone', 'label', 'address', 
            'reference', 'latitude', 'longitude', 'whatsapp_number', 
            'document_proof'
        ]
        widgets = {
            'location_type': forms.RadioSelect(
                attrs={'class': 'form-check-input'},
                choices=ProviderLocation.LOCATION_TYPE_CHOICES
            ),
            'city': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_city'
            }),
            'zone': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_zone'
            }),
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Sucursal Norte'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Referencia'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': True,
                'step': '0.000001'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': True,
                'step': '0.000001'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'tel',
                'placeholder': '+593 9 XXXXXXXXX'
            }),
            'document_proof': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.provider = kwargs.pop('provider', None)
        self.location_type_forced = kwargs.pop('location_type', None)
        super().__init__(*args, **kwargs)
        
        if self.location_type_forced:
            self.fields['location_type'].initial = self.location_type_forced
            self.fields['location_type'].disabled = True
    
    def clean(self):
        cleaned = super().clean()
        loc_type = cleaned.get('location_type')
        city = cleaned.get('city')
        latitude = cleaned.get('latitude')
        longitude = cleaned.get('longitude')
        
        if not latitude or not longitude:
            raise ValidationError("Debes seleccionar ubicación en el mapa")
        
        if loc_type == 'local' and self.provider and city:
            max_per_city = int(SystemConfig.get_config('max_provider_locations_per_city', 3))
            qs = ProviderLocation.objects.filter(
                provider=self.provider,
                city=city,
                location_type='local'
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.count() >= max_per_city:
                raise ValidationError(f'Límite de {max_per_city} locales alcanzado')
        
        if loc_type == 'base' and self.provider:
            qs = ProviderLocation.objects.filter(
                provider=self.provider,
                location_type='base'
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Solo un domicilio base permitido')
        
        return cleaned
