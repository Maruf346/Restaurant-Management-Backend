"""
apps/restaurants/views.py
─────────────────────────
Restaurant management views with role-based access.

  SUPER_ADMIN       → full CRUD on all restaurants
  RESTAURANT_ADMIN  → read-only access to their assigned restaurant(s)
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsSuperAdminOrReadOnly
from .mixins import RestaurantAccessMixin
from .models import Restaurant
from .serializers import RestaurantSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['restaurants'],
        summary='List restaurants',
        description='Super Admins see all restaurants; Restaurant Admins see only their assigned restaurant(s).',
        responses={200: RestaurantSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['restaurants'],
        summary='Get restaurant details',
        description='Return details for a single restaurant.',
        responses={200: RestaurantSerializer},
    ),
    create=extend_schema(
        tags=['restaurants'],
        summary='Create a restaurant',
        description='Super Admin only. Create a new restaurant.',
        request=RestaurantSerializer,
        responses={201: RestaurantSerializer},
    ),
    update=extend_schema(
        tags=['restaurants'],
        summary='Update a restaurant',
        description='Super Admin only. Replace all editable fields.',
        request=RestaurantSerializer,
        responses={200: RestaurantSerializer},
    ),
    partial_update=extend_schema(
        tags=['restaurants'],
        summary='Partially update a restaurant',
        description='Super Admin only. Update selected fields.',
        request=RestaurantSerializer,
        responses={200: RestaurantSerializer},
    ),
    destroy=extend_schema(
        tags=['restaurants'],
        summary='Delete a restaurant',
        description='Super Admin only. Delete a restaurant record.',
        responses={204: None},
    ),
)
class RestaurantViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    restaurant_filter_field = 'id'
    # Super Admins: full CRUD | Restaurant Admins: GET only
    permission_classes = [IsAuthenticated, IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset_by_restaurant(queryset)


# Backward-compatible alias
LocationViewSet = RestaurantViewSet
