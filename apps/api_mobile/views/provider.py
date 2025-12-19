from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from ..serializers.provider import (
    DashboardSerializer, DashboardStatsSerializer, OnboardingStepSerializer,
    ProviderProfileDetailSerializer, ProviderServiceSerializer
)
from ..permissions import IsProvider, IsVerifiedProvider
from ..utils import success_response, error_response
from apps.core.models import (
    ProviderProfile, Service, Booking, Review,
    ProviderLocation, ProviderSchedule, ProviderZoneCost
)


class DashboardView(APIView):
    """
    GET /api/v1/provider/dashboard/
    
    Dashboard del proveedor con métricas y estado de onboarding
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        user = request.user
        
        try:
            provider_profile = user.provider_profile
        except ProviderProfile.DoesNotExist:
            return error_response(
                "Perfil de proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # === Calcular estadísticas ===
        bookings = Booking.objects.filter(provider=user)
        completed_bookings = bookings.filter(status='completed')
        
        stats = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'completed_bookings': completed_bookings.count(),
            'total_earnings': completed_bookings.filter(
                payment_status='paid'
            ).aggregate(total=Sum('total_cost'))['total'] or 0,
            'active_balance': self._calculate_active_balance(user),
            'rating_avg': Review.objects.filter(
                booking__provider=user
            ).aggregate(avg=Avg('rating'))['avg'] or 0,
            'total_reviews': Review.objects.filter(booking__provider=user).count(),
        }
        
        # === Próximas reservas (48h) ===
        now = timezone.now()
        upcoming_limit = now + timedelta(hours=48)
        upcoming_bookings = bookings.filter(
            status='accepted',
            scheduled_time__gte=now,
            scheduled_time__lte=upcoming_limit
        ).order_by('scheduled_time')[:5]
        
        # === Reseñas recientes ===
        recent_reviews = Review.objects.filter(
            booking__provider=user
        ).select_related('customer', 'booking').order_by('-created_at')[:3]
        
        # === Onboarding ===
        onboarding_steps = self._get_onboarding_steps(provider_profile)
        onboarding_progress = self._calculate_onboarding_progress(onboarding_steps)
        
        # === Serializar respuesta ===
        from ..serializers.bookings import BookingListSerializer, ReviewSerializer
        
        dashboard_data = {
            'stats': stats,
            'upcoming_bookings': BookingListSerializer(
                upcoming_bookings, many=True, context={'request': request}
            ).data,
            'recent_reviews': ReviewSerializer(recent_reviews, many=True).data,
            'onboarding_progress': onboarding_progress,
            'onboarding_steps': onboarding_steps,
        }
        
        return success_response(data=dashboard_data)
    
    def _calculate_active_balance(self, user):
        """Calcula el saldo disponible para retiro"""
        # Lógica similar a la del dashboard web
        completed_paid = Booking.objects.filter(
            provider=user,
            status='completed',
            payment_status='paid'
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        # Restar retiros completados
        from apps.core.models import WithdrawalRequest
        withdrawals = WithdrawalRequest.objects.filter(
            provider=user,
            status='completed'
        ).aggregate(total=Sum('requested_amount'))['total'] or 0
        
        return max(0, completed_paid - withdrawals)
    
    def _get_onboarding_steps(self, provider_profile):
        """Genera los pasos del onboarding checklist"""
        user = provider_profile.user
        
        # Paso 0: Completar perfil
        profile_complete = bool(
            provider_profile.business_name and
            provider_profile.description and
            provider_profile.category_id and
            provider_profile.profile_photo
        )
        
        # Paso 1: Subir documentos
        documents_uploaded = bool(
            provider_profile.id_card_front and
            provider_profile.id_card_back and
            provider_profile.selfie_with_id
        )
        
        # Paso 2: Crear primer servicio
        has_service = Service.objects.filter(provider=user).exists()
        
        # Paso 3: Verificación aprobada
        is_approved = provider_profile.status == 'approved'
        is_rejected = provider_profile.status == 'rejected'
        is_pending = provider_profile.status in ['pending', 'resubmitted']
        
        # Paso 4: Ubicación base
        has_base_location = ProviderLocation.objects.filter(
            provider=user,
            location_type='base'
        ).exists()
        
        # Determinar si necesita cobertura y costos según modalidad
        service_mode = provider_profile.service_mode
        needs_coverage = service_mode in ['home', 'both']
        
        # Paso 5 (condicional): Zonas de cobertura
        has_coverage = provider_profile.coverage_zones.exists() if needs_coverage else True
        
        # Paso 6 (condicional): Costos de traslado configurados
        has_costs = ProviderZoneCost.objects.filter(provider=user).exists() if needs_coverage else True
        
        # Paso 7: Horarios configurados
        has_schedule = ProviderSchedule.objects.filter(provider=user, is_active=True).exists()
        
        # Construir steps base (comunes a todas las modalidades)
        steps = [
            {
                'id': 0,
                'label': 'Completar perfil del negocio',
                'done': profile_complete,
                'status': 'done' if profile_complete else 'pending',
                'locked': False,
                'url': None,
            },
            {
                'id': 1,
                'label': 'Subir documentos de identidad',
                'done': documents_uploaded,
                'status': 'done' if documents_uploaded else 'pending',
                'locked': not profile_complete,
                'url': None,
            },
            {
                'id': 2,
                'label': 'Publicar primer servicio',
                'done': has_service,
                'status': 'done' if has_service else 'pending',
                'locked': not documents_uploaded,
                'url': None,
            },
            {
                'id': 3,
                'label': 'Verificación de perfil',
                'done': is_approved,
                'status': 'done' if is_approved else ('rejected' if is_rejected else ('processing' if is_pending else 'pending')),
                'locked': not has_service,
                'url': None,
                'is_processing': is_pending,
                'is_rejected': is_rejected,
            },
            {
                'id': 4,
                'label': 'Configurar ubicación base',
                'done': has_base_location,
                'status': 'done' if has_base_location else 'pending',
                'locked': not is_approved,
                'url': None,
            },
        ]
        
        # Agregar pasos condicionales solo si la modalidad lo requiere
        if needs_coverage:
            steps.extend([
                {
                    'id': 5,
                    'label': 'Definir zonas de cobertura',
                    'done': has_coverage,
                    'status': 'done' if has_coverage else 'pending',
                    'locked': not has_base_location,
                    'url': None,
                },
                {
                    'id': 6,
                    'label': 'Configurar costos de traslado',
                    'done': has_costs,
                    'status': 'done' if has_costs else 'pending',
                    'locked': not has_coverage,
                    'url': None,
                },
            ])
        
        # Paso final: horarios (siempre presente)
        # El locked depende de si necesita o no coverage
        steps.append({
            'id': 7,
            'label': 'Publicar horarios de atención',
            'done': has_schedule,
            'status': 'done' if has_schedule else 'pending',
            'locked': not (has_costs if needs_coverage else has_base_location),
            'url': None,
        })
        
        return steps
    
    def _calculate_onboarding_progress(self, steps):
        """Calcula el porcentaje de onboarding completado"""
        completed = sum(1 for step in steps if step['done'])
        total = len(steps)
        return int((completed / total) * 100)


class ProfileView(APIView):
    """
    GET/PATCH /api/v1/provider/profile/
    
    Ver y actualizar perfil de proveedor
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        try:
            provider_profile = request.user.provider_profile
            serializer = ProviderProfileDetailSerializer(
                provider_profile,
                context={'request': request}
            )
            return success_response(data=serializer.data)
        except ProviderProfile.DoesNotExist:
            return error_response(
                "Perfil de proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
    
    def patch(self, request):
        try:
            provider_profile = request.user.provider_profile
            user = request.user
            
            # Actualizar datos del usuario si vienen
            if 'first_name' in request.data:
                user.first_name = request.data['first_name']
            if 'last_name' in request.data:
                user.last_name = request.data['last_name']
            if 'phone' in request.data:
                user.profile.phone = request.data['phone']
                user.profile.save()
            user.save()
            
            # Actualizar provider profile
            serializer = ProviderProfileDetailSerializer(
                provider_profile,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return success_response(
                    data=serializer.data,
                    message="Perfil actualizado exitosamente"
                )
            
            return error_response(
                "Datos inválidos",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        except ProviderProfile.DoesNotExist:
            return error_response(
                "Perfil de proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )


class ServiceListCreateView(APIView):
    """
    GET/POST /api/v1/provider/services/
    
    Listar y crear servicios del proveedor
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        services = Service.objects.filter(provider=request.user)
        serializer = ProviderServiceSerializer(
            services,
            many=True,
            context={'request': request}
        )
        return success_response(data=serializer.data)
    
    def post(self, request):
        # Verificar que el proveedor puede publicar servicios
        try:
            provider_profile = request.user.provider_profile
            if not provider_profile.can_publish_services():
                return error_response(
                    "Debes configurar tu ubicación antes de publicar servicios",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        except:
            pass
        
        # Crear servicio
        serializer = ProviderServiceSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            service = serializer.save(provider=request.user)
            
            # Triggear validación si corresponde
            from apps.core.verification import trigger_validation_if_eligible
            trigger_validation_if_eligible(request.user)
            
            return success_response(
                data=serializer.data,
                message="Servicio creado exitosamente",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            "Datos inválidos",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class ServiceDetailView(APIView):
    """
    PATCH/DELETE /api/v1/provider/services/{service_id}/
    
    Actualizar y eliminar servicio
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def patch(self, request, service_id):
        try:
            service = Service.objects.get(id=service_id, provider=request.user)
        except Service.DoesNotExist:
            return error_response(
                "Servicio no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProviderServiceSerializer(
            service,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return success_response(
                data=serializer.data,
                message="Servicio actualizado exitosamente"
            )
        
        return error_response(
            "Datos inválidos",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def delete(self, request, service_id):
        try:
            service = Service.objects.get(id=service_id, provider=request.user)
            
            # Verificar que no tenga reservas activas
            active_bookings = Booking.objects.filter(
                service=service,
                status__in=['pending', 'accepted']
            ).exists()
            
            if active_bookings:
                return error_response(
                    "No puedes eliminar un servicio con reservas activas",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            service.delete()
            return success_response(
                message="Servicio eliminado exitosamente",
                status_code=status.HTTP_204_NO_CONTENT
            )
            
        except Service.DoesNotExist:
            return error_response(
                "Servicio no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )
