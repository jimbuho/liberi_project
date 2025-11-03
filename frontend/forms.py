# forms.py - Formularios para el sistema de pagos

from django import forms
from django.core.exceptions import ValidationError
from datetime import date

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