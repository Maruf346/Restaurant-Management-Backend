from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Location
from .serializers import LocationSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['locations'],
        summary='List locations',
        description='Return all restaurant locations available to the authenticated user.',
        responses={200: LocationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['locations'],
        summary='Get location details',
        description='Return details for a single restaurant location.',
        responses={200: LocationSerializer},
    ),
    create=extend_schema(
        tags=['locations'],
        summary='Create a location',
        description='Create a new restaurant location with its metadata.',
        request=LocationSerializer,
        responses={201: LocationSerializer},
    ),
    update=extend_schema(
        tags=['locations'],
        summary='Update a location',
        description='Replace all editable fields for a restaurant location.',
        request=LocationSerializer,
        responses={200: LocationSerializer},
    ),
    partial_update=extend_schema(
        tags=['locations'],
        summary='Partially update a location',
        description='Update selected fields on a restaurant location.',
        request=LocationSerializer,
        responses={200: LocationSerializer},
    ),
    destroy=extend_schema(
        tags=['locations'],
        summary='Delete a location',
        description='Delete a restaurant location record permanently.',
        responses={204: None},
    ),
)
class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
