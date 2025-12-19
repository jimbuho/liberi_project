from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from decimal import Decimal

from ..serializers.provider import (
    BankSerializer, ProviderBankAccountSerializer, WithdrawalSerializer
)
from ..permissions import IsProvider
from ..throttling import WithdrawalRateThrottle
from ..utils import success_response, error_response
from apps.core.models import Bank, ProviderBankAccount, WithdrawalRequest, Booking
from django.conf import settings
from django.db.models import Sum


class BankListView(APIView):
    """
    GET /api/v1/provider/banks/
    
    Listar bancos disponibles
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        banks = Bank.objects.filter(is_active=True).order_by('name')
        serializer = BankSerializer(banks, many=True)
        return success_response(data=serializer.data)


class BankAccountListCreateView(APIView):
    """
    GET/POST /api/v1/provider/bank-accounts/
    
    Listar y crear cuentas bancarias
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        accounts = ProviderBankAccount.objects.filter(
            provider=request.user
        ).select_related('bank').order_by('-is_primary', '-created_at')
        
        serializer = ProviderBankAccountSerializer(accounts, many=True)
        return success_response(data=serializer.data)
    
    def post(self, request):
        # Validar datos requeridos
        required_fields = ['bank_id', 'account_type', 'account_number', 'owner_fullname']
        for field in required_fields:
            if field not in request.data:
                return error_response(
                    f"Campo requerido: {field}",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            bank = Bank.objects.get(id=request.data['bank_id'])
        except Bank.DoesNotExist:
            return error_response(
                "Banco no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Crear cuenta
        account_number = request.data['account_number']
        
        # Validar que no exista duplicada
        if ProviderBankAccount.objects.filter(
            provider=request.user,
            account_number_masked=self._mask_account_number(account_number)
        ).exists():
            return error_response(
                "Ya tienes esta cuenta bancaria registrada",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Si es la primera cuenta, hacerla principal
        is_first = not ProviderBankAccount.objects.filter(provider=request.user).exists()
        is_primary = request.data.get('is_primary', is_first)
        
        # Si se marca como principal, desmarcar otras
        if is_primary:
            ProviderBankAccount.objects.filter(
                provider=request.user,
                is_primary=True
            ).update(is_primary=False)
        
        # Crear cuenta
        account = ProviderBankAccount.objects.create(
            provider=request.user,
            bank=bank,
            account_type=request.data['account_type'],
            account_number_masked=self._mask_account_number(account_number),
            account_number_encrypted=self._encrypt_account_number(account_number),
            owner_fullname=request.data['owner_fullname'],
            is_primary=is_primary
        )
        
        serializer = ProviderBankAccountSerializer(account)
        return success_response(
            data=serializer.data,
            message="Cuenta bancaria agregada exitosamente",
            status_code=status.HTTP_201_CREATED
        )
    
    def _mask_account_number(self, account_number):
        """Enmascara el número de cuenta"""
        if len(account_number) > 8:
            return f"{account_number[:4]}{'*' * (len(account_number) - 8)}{account_number[-4:]}"
        return account_number
    
    def _encrypt_account_number(self, account_number):
        """
        Cifra el número de cuenta
        TODO: Implementar cifrado real (Fernet, AES, etc.)
        Por ahora solo almacena el número
        """
        return account_number


class BankAccountDetailView(APIView):
    """
    DELETE /api/v1/provider/bank-accounts/{account_id}/
    
    Eliminar cuenta bancaria
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def delete(self, request, account_id):
        try:
            account = ProviderBankAccount.objects.get(
                id=account_id,
                provider=request.user
            )
        except ProviderBankAccount.DoesNotExist:
            return error_response(
                "Cuenta no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # No permitir eliminar si tiene retiros pendientes
        pending_withdrawals = WithdrawalRequest.objects.filter(
            provider_bank_account=account,
            status='pending'
        ).exists()
        
        if pending_withdrawals:
            return error_response(
                "No puedes eliminar una cuenta con retiros pendientes",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        account.delete()
        return success_response(
            message="Cuenta bancaria eliminada",
            status_code=status.HTTP_204_NO_CONTENT
        )


class WithdrawalListView(APIView):
    """
    GET /api/v1/provider/withdrawals/
    
    Listar historial de retiros
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        withdrawals = WithdrawalRequest.objects.filter(
            provider=request.user
        ).select_related('provider_bank_account__bank').order_by('-created_at')
        
        serializer = WithdrawalSerializer(withdrawals, many=True)
        return success_response(data=serializer.data)


class WithdrawalCreateView(APIView):
    """
    POST /api/v1/provider/withdrawals/
    
    Solicitar nuevo retiro
    """
    permission_classes = [IsAuthenticated, IsProvider]
    throttle_classes = [WithdrawalRateThrottle]
    
    def post(self, request):
        # Validar monto
        requested_amount = request.data.get('requested_amount')
        
        if not requested_amount:
            return error_response(
                "Monto requerido",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requested_amount = Decimal(str(requested_amount))
        except:
            return error_response(
                "Monto inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if requested_amount <= 0:
            return error_response(
                "El monto debe ser mayor a 0",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Calcular balance disponible
        completed_paid = Booking.objects.filter(
            provider=request.user,
            status='completed',
            payment_status='paid'
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
        
        previous_withdrawals = WithdrawalRequest.objects.filter(
            provider=request.user,
            status__in=['pending', 'completed']
        ).aggregate(total=Sum('requested_amount'))['total'] or Decimal('0')
        
        available_balance = completed_paid - previous_withdrawals
        
        if requested_amount > available_balance:
            return error_response(
                f"Saldo insuficiente. Disponible: ${available_balance}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar cuenta bancaria
        bank_account_id = request.data.get('bank_account_id')
        
        if bank_account_id:
            try:
                bank_account = ProviderBankAccount.objects.get(
                    id=bank_account_id,
                    provider=request.user
                )
            except ProviderBankAccount.DoesNotExist:
                return error_response(
                    "Cuenta bancaria no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND
                )
        else:
            # Usar cuenta principal
            bank_account = ProviderBankAccount.objects.filter(
                provider=request.user,
                is_primary=True
            ).first()
            
            if not bank_account:
                return error_response(
                    "Debes tener al menos una cuenta bancaria registrada",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # Calcular comisión
        commission_percent = Decimal(str(
            settings.LIBERI_WITHDRAWAL_COMMISSION_PERCENT
        ))
        commission_amount = (requested_amount * commission_percent) / Decimal('100')
        amount_payable = requested_amount - commission_amount
        
        # Validar límite semanal (si está configurado)
        # TODO: Implementar validación de límite semanal
        
        # Validar máximo por día
        from django.utils import timezone
        today = timezone.now().date()
        today_withdrawals = WithdrawalRequest.objects.filter(
            provider=request.user,
            created_at__date=today
        ).count()
        
        max_per_day = settings.LIBERI_WITHDRAWAL_MAX_PER_DAY
        if today_withdrawals >= max_per_day:
            return error_response(
                f"Has alcanzado el límite de {max_per_day} retiros por día",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Crear solicitud
        withdrawal = WithdrawalRequest.objects.create(
            provider=request.user,
            provider_bank_account=bank_account,
            requested_amount=requested_amount,
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            amount_payable=amount_payable,
            description=request.data.get('description', ''),
            status='pending'
        )
        
        # Notificar al admin (email)
        try:
            from apps.core.tasks import notify_admin_new_withdrawal
            notify_admin_new_withdrawal.delay(withdrawal.id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error notificando retiro: {e}")
        
        serializer = WithdrawalSerializer(withdrawal)
        return success_response(
            data=serializer.data,
            message="Solicitud de retiro creada exitosamente",
            status_code=status.HTTP_201_CREATED
        )
