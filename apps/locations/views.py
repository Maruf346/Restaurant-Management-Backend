"""
apps/locations/views.py
────────────────────────
Location management views with role-based access.

  SUPER_ADMIN       → full CRUD on all locations
  RESTAURANT_ADMIN  → read-only access to their assigned location(s)
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsSuperAdminOrReadOnly
from .mixins import LocationAccessMixin
from .models import Location
from .serializers import LocationSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['locations'],
        summary='List locations',
        description='Super Admins see all locations; Restaurant Admins see only their assigned location(s).',
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
        description='Super Admin only. Create a new restaurant location.',
        request=LocationSerializer,
        responses={201: LocationSerializer},
    ),
    update=extend_schema(
        tags=['locations'],
        summary='Update a location',
        description='Super Admin only. Replace all editable fields.',
        request=LocationSerializer,
        responses={200: LocationSerializer},
    ),
    partial_update=extend_schema(
        tags=['locations'],
        summary='Partially update a location',
        description='Super Admin only. Update selected fields.',
        request=LocationSerializer,
        responses={200: LocationSerializer},
    ),
    destroy=extend_schema(
        tags=['locations'],
        summary='Delete a location',
        description='Super Admin only. Delete a restaurant location record.',
        responses={204: None},
    ),
)
class LocationViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    location_filter_field = 'id'
    # Super Admins: full CRUD | Restaurant Admins: GET only
    permission_classes = [IsAuthenticated, IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset_by_location(queryset)
