from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LightspeedConfig
from .serializers import LightspeedConfigSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['pos_lightspeed'],
        summary='List Lightspeed configurations',
        description='Return the Lightspeed POS configuration entries for each restaurant location.',
        responses={200: LightspeedConfigSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['pos_lightspeed'],
        summary='Get Lightspeed configuration',
        description='Return a single Lightspeed POS configuration record.',
        responses={200: LightspeedConfigSerializer},
    ),
    create=extend_schema(
        tags=['pos_lightspeed'],
        summary='Create Lightspeed configuration',
        description='Configure a restaurant location for Lightspeed POS sync.',
        request=LightspeedConfigSerializer,
        responses={201: LightspeedConfigSerializer},
    ),
    update=extend_schema(
        tags=['pos_lightspeed'],
        summary='Update Lightspeed configuration',
        request=LightspeedConfigSerializer,
        responses={200: LightspeedConfigSerializer},
    ),
    partial_update=extend_schema(
        tags=['pos_lightspeed'],
        summary='Partially update Lightspeed configuration',
        request=LightspeedConfigSerializer,
        responses={200: LightspeedConfigSerializer},
    ),
    destroy=extend_schema(
        tags=['pos_lightspeed'],
        summary='Delete Lightspeed configuration',
        responses={204: None},
    ),
)
class LightspeedConfigViewSet(viewsets.ModelViewSet):
    queryset = LightspeedConfig.objects.select_related('location').all()
    serializer_class = LightspeedConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset
