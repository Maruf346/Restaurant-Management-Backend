"""
apps/inventory/views.py
────────────────────────
Inventory viewsets with restaurant-level access control.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.restaurants.mixins import RestaurantAccessMixin
from apps.users.permissions import IsSuperAdminOrReadOnly
from .models import Ingredient, PurchaseEntry
from .serializers import IngredientSerializer, PurchaseEntrySerializer


@extend_schema_view(
    list=extend_schema(
        tags=['inventory'],
        summary='List ingredients',
        description='Return ingredients for the authenticated user\'s accessible restaurants.',
        responses={200: IngredientSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['inventory'],
        summary='Get ingredient details',
        description='Return the full ingredient record and stock details.',
        responses={200: IngredientSerializer},
    ),
    create=extend_schema(
        tags=['inventory'],
        summary='Create ingredient',
        description='Add a new ingredient and set its baseline stock and purchasing details.',
        request=IngredientSerializer,
        responses={201: IngredientSerializer},
    ),
    update=extend_schema(
        tags=['inventory'],
        summary='Update ingredient',
        request=IngredientSerializer,
        responses={200: IngredientSerializer},
    ),
    partial_update=extend_schema(
        tags=['inventory'],
        summary='Partially update ingredient',
        request=IngredientSerializer,
        responses={200: IngredientSerializer},
    ),
    destroy=extend_schema(
        tags=['inventory'],
        summary='Delete ingredient',
        responses={204: None},
    ),
)
class IngredientViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = Ingredient.objects.select_related('restaurant').all()
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated]
    restaurant_filter_field = 'restaurant_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.request.query_params.get('restaurant') or self.request.query_params.get('location')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if restaurant:
            self.assert_restaurant_access(restaurant.id)
        serializer.save()


@extend_schema_view(
    list=extend_schema(
        tags=['inventory'],
        summary='List purchase entries',
        description='Return purchase history for the accessible restaurants.',
        responses={200: PurchaseEntrySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['inventory'],
        summary='Get purchase entry',
        responses={200: PurchaseEntrySerializer},
    ),
    create=extend_schema(
        tags=['inventory'],
        summary='Create purchase entry',
        request=PurchaseEntrySerializer,
        responses={201: PurchaseEntrySerializer},
    ),
    update=extend_schema(
        tags=['inventory'],
        summary='Update purchase entry',
        request=PurchaseEntrySerializer,
        responses={200: PurchaseEntrySerializer},
    ),
    partial_update=extend_schema(
        tags=['inventory'],
        summary='Partially update purchase entry',
        request=PurchaseEntrySerializer,
        responses={200: PurchaseEntrySerializer},
    ),
    destroy=extend_schema(
        tags=['inventory'],
        summary='Delete purchase entry',
        responses={204: None},
    ),
)
class PurchaseEntryViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = PurchaseEntry.objects.select_related('restaurant', 'ingredient', 'created_by').all()
    serializer_class = PurchaseEntrySerializer
    permission_classes = [IsAuthenticated]
    restaurant_filter_field = 'restaurant_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.request.query_params.get('restaurant') or self.request.query_params.get('location')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if restaurant:
            self.assert_restaurant_access(restaurant.id)
        serializer.save(created_by=self.request.user)
