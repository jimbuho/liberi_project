from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ..serializers.provider import (
    ProviderLocationDetailSerializer, ZoneCostSerializer,
    ScheduleSerializer, UnavailabilitySerializer
)
from ..permissions import IsProvider
from ..utils import success_response, error_response
from apps.core.models import (
    ProviderLocation, ProviderZoneCost, Zone,
    ProviderSchedule, ProviderUnavailability, Booking
)


class LocationListCreateView(APIView):
    """
    GET/POST /api/v1/provider/locations/
    
    Listar y crear ubicaciones del proveedor
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        locations = ProviderLocation.objects.filter(
            provider=request.user
        ).select_related('city', 'zone').order_by('location_type', 'label')
        
        base_location = locations.filter(location_type='base').first()
        local_locations = locations.filter(location_type='local')
        
        serializer = ProviderLocationDetailSerializer(
            locations,
            many=True,
            context={'request': request}
        )
        
        return success_response(data={
            'base_location': ProviderLocationDetailSerializer(
                base_location, context={'request': request}
            ).data if base_location else None,
            'local_locations': ProviderLocationDetailSerializer(
                local_locations, many=True, context={'request': request}
            ).data
        })
    
    def post(self, request):
        serializer = ProviderLocationDetailSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            location = serializer.save(provider=request.user)
            return success_response(
                data=serializer.data,
                message="Ubicación creada exitosamente",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            "Datos inválidos",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class LocationDetailView(APIView):
    """
    DELETE /api/v1/provider/locations/{location_id}/
    
    Eliminar ubicación
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def delete(self, request, location_id):
        try:
            location = ProviderLocation.objects.get(
                id=location_id,
                provider=request.user
            )
        except ProviderLocation.DoesNotExist:
            return error_response(
                "Ubicación no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que no tenga reservas activas
        active_bookings = Booking.objects.filter(
            provider_location=location,
            status__in=['pending', 'accepted']
        ).exists()
        
        if active_bookings:
            return error_response(
                "No puedes eliminar una ubicación con reservas activas",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        location.delete()
        return success_response(
            message="Ubicación eliminada exitosamente",
            status_code=status.HTTP_204_NO_CONTENT
        )


class ServiceModeView(APIView):
    """
    PATCH /api/v1/provider/service-mode/
    
    Cambiar modalidad de atención (home/local/both)
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    # Descripciones claras de cada modalidad
    MODE_DESCRIPTIONS = {
        'home': 'Solo a domicilio - Atiendes en la ubicación del cliente',
        'local': 'Solo en local - Los clientes vienen a tu establecimiento',
        'both': 'En local y a domicilio - Ofreces ambas opciones'
    }
    
    def patch(self, request):
        service_mode = request.data.get('service_mode')
        
        if service_mode not in ['home', 'local', 'both']:
            return error_response(
                "Modalidad inválida. Opciones: home, local, both",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            provider_profile = request.user.provider_profile
            provider_profile.service_mode = service_mode
            provider_profile.save()
            
            # Indicar qué configuraciones requiere esta modalidad
            requires_coverage = service_mode in ['home', 'both']
            requires_travel_costs = service_mode in ['home', 'both']
            
            return success_response(
                data={
                    'service_mode': service_mode,
                    'description': self.MODE_DESCRIPTIONS[service_mode],
                    'requires_coverage': requires_coverage,
                    'requires_travel_costs': requires_travel_costs
                },
                message=f"Modalidad actualizada: {self.MODE_DESCRIPTIONS[service_mode]}"
            )
        except:
            return error_response(
                "Error al actualizar modalidad",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CoverageListView(APIView):
    """
    GET /api/v1/provider/coverage/
    
    Obtener zonas de cobertura del proveedor
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        try:
            provider_profile = request.user.provider_profile
            
            # Zonas cubiertas
            covered_zones = provider_profile.coverage_zones.all()
            
            # Zonas disponibles (de la ciudad del proveedor)
            # Obtener ciudad desde ubicación base
            base_location = ProviderLocation.objects.filter(
                provider=request.user,
                location_type='base'
            ).first()
            
            available_zones = []
            if base_location and base_location.city:
                available_zones = Zone.objects.filter(
                    city=base_location.city,
                    active=True
                )
            
            from ..serializers.services import ZoneSerializer
            
            return success_response(data={
                'covered_zones': ZoneSerializer(covered_zones, many=True).data,
                'available_zones': ZoneSerializer(available_zones, many=True).data
            })
        except:
            return error_response(
                "Error al obtener zonas",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CoverageDetailView(APIView):
    """
    POST/DELETE /api/v1/provider/coverage/{zone_id}/
    
    Agregar o remover zona de cobertura
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request, zone_id):
        try:
            zone = Zone.objects.get(id=zone_id)
            provider_profile = request.user.provider_profile
            
            provider_profile.coverage_zones.add(zone)
            
            # Crear ProviderZoneCost con costo 0 por defecto
            ProviderZoneCost.objects.get_or_create(
                provider=request.user,
                zone=zone,
                defaults={'travel_cost': 0}
            )
            
            return success_response(
                message="Zona agregada a cobertura"
            )
        except Zone.DoesNotExist:
            return error_response(
                "Zona no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, zone_id):
        try:
            zone = Zone.objects.get(id=zone_id)
            provider_profile = request.user.provider_profile
            
            # Validar que no tenga reservas activas en esa zona
            active_bookings = Booking.objects.filter(
                provider=request.user,
                location__zone=zone,
                status__in=['pending', 'accepted']
            ).exists()
            
            if active_bookings:
                return error_response(
                    "No puedes remover una zona con reservas activas",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            provider_profile.coverage_zones.remove(zone)
            
            # Eliminar costo asociado
            ProviderZoneCost.objects.filter(
                provider=request.user,
                zone=zone
            ).delete()
            
            return success_response(
                message="Zona removida de cobertura",
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Zone.DoesNotExist:
            return error_response(
                "Zona no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )


class ZoneCostView(APIView):
    """
    PATCH /api/v1/provider/zone-costs/{zone_id}/
    
    Actualizar costo de traslado para una zona
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def patch(self, request, zone_id):
        travel_cost = request.data.get('travel_cost')
        
        if travel_cost is None:
            return error_response(
                "travel_cost es requerido",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            zone_cost = ProviderZoneCost.objects.get(
                provider=request.user,
                zone_id=zone_id
            )
            
            zone_cost.travel_cost = travel_cost
            zone_cost.full_clean()  # Validar límites
            zone_cost.save()
            
            serializer = ZoneCostSerializer(zone_cost)
            return success_response(
                data=serializer.data,
                message="Costo actualizado exitosamente"
            )
        except ProviderZoneCost.DoesNotExist:
            return error_response(
                "Zona no encontrada en tu cobertura",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return error_response(
                str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )


class ScheduleListCreateView(APIView):
    """
    GET/POST /api/v1/provider/schedule/
    
    Listar y crear horarios
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        schedules = ProviderSchedule.objects.filter(
            provider=request.user,
            is_active=True
        ).order_by('day_of_week', 'start_time')
        
        unavailabilities = ProviderUnavailability.objects.filter(
            provider=request.user
        ).order_by('-start_date')
        
        return success_response(data={
            'schedules': ScheduleSerializer(schedules, many=True).data,
            'unavailabilities': UnavailabilitySerializer(unavailabilities, many=True).data
        })
    
    def post(self, request):
        serializer = ScheduleSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(provider=request.user)
            return success_response(
                data=serializer.data,
                message="Horario creado exitosamente",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            "Datos inválidos",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class ScheduleDetailView(APIView):
    """
    DELETE /api/v1/provider/schedule/{schedule_id}/
    
    Eliminar horario
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def delete(self, request, schedule_id):
        try:
            schedule = ProviderSchedule.objects.get(
                id=schedule_id,
                provider=request.user
            )
            schedule.delete()
            return success_response(
                message="Horario eliminado exitosamente",
                status_code=status.HTTP_204_NO_CONTENT
            )
        except ProviderSchedule.DoesNotExist:
            return error_response(
                "Horario no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )


class UnavailabilityListCreateView(APIView):
    """
    GET/POST /api/v1/provider/unavailability/
    
    Listar y crear períodos de inactividad
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def get(self, request):
        unavailabilities = ProviderUnavailability.objects.filter(
            provider=request.user
        ).order_by('-start_date')
        
        serializer = UnavailabilitySerializer(unavailabilities, many=True)
        return success_response(data=serializer.data)
    
    def post(self, request):
        serializer = UnavailabilitySerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(provider=request.user)
            return success_response(
                data=serializer.data,
                message="Período de inactividad creado exitosamente",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            "Datos inválidos",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class UnavailabilityDetailView(APIView):
    """
    DELETE /api/v1/provider/unavailability/{id}/
    
    Eliminar período de inactividad
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def delete(self, request, unavailability_id):
        try:
            unavailability = ProviderUnavailability.objects.get(
                id=unavailability_id,
                provider=request.user
            )
            unavailability.delete()
            return success_response(
                message="Período eliminado exitosamente",
                status_code=status.HTTP_204_NO_CONTENT
            )
        except ProviderUnavailability.DoesNotExist:
            return error_response(
                "Período no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )


class ToggleActiveView(APIView):
    """
    POST /api/v1/provider/toggle-active/
    
    Activar/desactivar disponibilidad del proveedor
    """
    permission_classes = [IsAuthenticated, IsProvider]
    
    def post(self, request):
        try:
            provider_profile = request.user.provider_profile
            provider_profile.is_active = not provider_profile.is_active
            provider_profile.save()
            
            return success_response(
                data={'is_active': provider_profile.is_active},
                message=f"Ahora estás {'activo' if provider_profile.is_active else 'inactivo'}"
            )
        except:
            return error_response(
                "Error al cambiar estado",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
