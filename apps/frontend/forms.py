# forms.py - Formularios para el sistema de pagos

from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from apps.core.models import ProviderLocation, ProviderProfile, SystemConfig

class BankTransferForm(forms.Form):
    """
    Formulario para registrar una transferencia bancaria
    """
    reference_number = forms.CharField(
        max_length=100,
        required=False,
        label='Número de Referencia',
        help_text='Número de comprobante o referencia de la transferencia',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 123456789'
        })
    )
    
    transfer_date = forms.DateField(
        required=False,
        label='Fecha de Transferencia',
        help_text='Fecha en que realizaste la transferencia',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    receipt = forms.FileField(
        required=False,
        label='Comprobante de Pago',
        help_text='Sube una foto o PDF del comprobante (opcional)',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,application/pdf'
        })
    )
    
    notes = forms.CharField(
        required=False,
        label='Notas Adicionales',
        help_text='Información adicional que nos ayude a identificar tu pago',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ej: Transferí desde Banco Pichincha, cuenta terminada en 1234'
        })
    )
    
    def clean_transfer_date(self):
        """
        Validar que la fecha de transferencia no sea futura
        """
        transfer_date = self.cleaned_data.get('transfer_date')
        
        if transfer_date and transfer_date > date.today():
            raise ValidationError('La fecha de transferencia no puede ser futura.')
        
        return transfer_date
    
    def clean_receipt(self):
        """
        Validar el tamaño y tipo de archivo del comprobante
        """
        receipt = self.cleaned_data.get('receipt')
        
        if receipt:
            # Validar tamaño (máximo 5MB)
            if receipt.size > 5 * 1024 * 1024:
                raise ValidationError('El archivo no puede superar los 5MB.')
            
            # Validar tipo de archivo
            allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
            if receipt.content_type not in allowed_types:
                raise ValidationError('Solo se permiten archivos JPG, PNG o PDF.')
        
        return receipt


class PaymentValidationForm(forms.Form):
    """
    Formulario para que los administradores validen pagos
    (Usado en el admin si se necesita)
    """
    validation_notes = forms.CharField(
        required=False,
        label='Notas de Validación',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas sobre la validación del pago'
        })
    )
    
    approve = forms.BooleanField(
        required=False,
        label='Aprobar Pago'
    )

# ============================================
# NUEVOS FORMULARIOS
# ============================================

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