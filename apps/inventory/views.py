"""
apps/inventory/views.py
────────────────────────
Inventory viewsets with restaurant-level access control.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.restaurants.mixins import RestaurantAccessMixin
from apps.users.permissions import IsSuperAdminOrReadOnly
from .models import Ingredient, PurchaseEntry
from .serializers import IngredientSerializer, PurchaseEntrySerializer
from .services import delete_purchase_entry


@extend_schema_view(
    list=extend_schema(
        tags=['inventory'],
        summary='List ingredients',
        description='Return ingredients for the authenticated user\'s accessible restaurants.',
        parameters=[
            OpenApiParameter('restaurant_id', str, description='Filter by restaurant UUID'),
            OpenApiParameter('name', str, description='Filter by ingredient name (contains)'),
            OpenApiParameter('supplier_name', str, description='Filter by supplier name (contains)'),
            OpenApiParameter('is_active', bool, description='Filter by active status (true/false)'),
        ],
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
        restaurant_id = self.get_requested_restaurant_id()
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)

        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)

        supplier_name = self.request.query_params.get('supplier_name')
        if supplier_name:
            queryset = queryset.filter(supplier_name__icontains=supplier_name)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if str(is_active).lower() in ('true', '1'):
                queryset = queryset.filter(is_active=True)
            elif str(is_active).lower() in ('false', '0'):
                queryset = queryset.filter(is_active=False)

        return queryset

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if restaurant:
            self.assert_restaurant_access(restaurant.id)
        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        self.assert_restaurant_access(instance.restaurant_id)
        serializer.save()

    def perform_destroy(self, instance):
        self.assert_restaurant_access(instance.restaurant_id)
        super().perform_destroy(instance)

    @extend_schema(
        tags=['inventory'],
        summary='Get purchase history for ingredient',
        description='Return all purchase entries for the specified ingredient UUID.',
        responses={200: PurchaseEntrySerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='purchases')
    def purchases(self, request, pk=None):
        ingredient = self.get_object()
        purchases = (
            PurchaseEntry.objects.filter(ingredient=ingredient)
            .select_related('restaurant', 'ingredient', 'created_by')
            .order_by('-purchase_date', '-created_at')
        )
        page = self.paginate_queryset(purchases)
        if page is not None:
            serializer = PurchaseEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PurchaseEntrySerializer(purchases, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=['inventory'],
        summary='List purchase entries',
        description='Return purchase history for the accessible restaurants.',
        parameters=[
            OpenApiParameter('restaurant_id', str, description='Filter by restaurant UUID'),
            OpenApiParameter('ingredient', str, description='Filter by ingredient UUID'),
            OpenApiParameter('supplier_name', str, description='Filter by supplier name (contains)'),
            OpenApiParameter('date_from', str, description='Filter purchases from date (YYYY-MM-DD)'),
            OpenApiParameter('date_to', str, description='Filter purchases up to date (YYYY-MM-DD)'),
        ],
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
        restaurant_id = self.get_requested_restaurant_id()
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)

        ingredient_id = self.request.query_params.get('ingredient') or self.request.query_params.get('ingredient_id')
        if ingredient_id:
            queryset = queryset.filter(ingredient_id=ingredient_id)

        supplier_name = self.request.query_params.get('supplier_name')
        if supplier_name:
            queryset = queryset.filter(supplier_name__icontains=supplier_name)

        date_from = self.request.query_params.get('date_from') or self.request.query_params.get('start_date')
        if date_from:
            queryset = queryset.filter(purchase_date__gte=date_from)

        date_to = self.request.query_params.get('date_to') or self.request.query_params.get('end_date')
        if date_to:
            queryset = queryset.filter(purchase_date__lte=date_to)

        return queryset

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if restaurant:
            self.assert_restaurant_access(restaurant.id)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        self.assert_restaurant_access(instance.restaurant_id)
        serializer.save()

    def perform_destroy(self, instance):
        self.assert_restaurant_access(instance.restaurant_id)
        delete_purchase_entry(instance)
