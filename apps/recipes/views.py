"""
apps/recipes/views.py
──────────────────────
Recipe viewsets with restaurant-level access control.
"""

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.restaurants.mixins import RestaurantAccessMixin
from .models import Category, Product, RecipeItem
from .serializers import CategorySerializer, ProductSerializer, RecipeItemSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List categories',
        description='Return menu categories for the accessible restaurant(s).',
        responses={200: CategorySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get category',
        responses={200: CategorySerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create category',
        request=CategorySerializer,
        responses={201: CategorySerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update category',
        request=CategorySerializer,
        responses={200: CategorySerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update category',
        request=CategorySerializer,
        responses={200: CategorySerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete category',
        responses={204: None},
    ),
)
class CategoryViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = (
        Category.objects.select_related('restaurant')
        .prefetch_related(
            Prefetch(
                'products',
                queryset=Product.objects.prefetch_related(
                    Prefetch('recipe_items', queryset=RecipeItem.objects.select_related('ingredient'))
                ),
            )
        )
        .all()
    )
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    restaurant_filter_field = 'restaurant_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.get_requested_restaurant_id()
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
        tags=['recipes'],
        summary='List recipe items',
        description='Return recipe ingredient rows for menu items.',
        responses={200: RecipeItemSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get recipe item',
        responses={200: RecipeItemSerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create recipe item',
        request=RecipeItemSerializer,
        responses={201: RecipeItemSerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update recipe item',
        request=RecipeItemSerializer,
        responses={200: RecipeItemSerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update recipe item',
        request=RecipeItemSerializer,
        responses={200: RecipeItemSerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete recipe item',
        responses={204: None},
    ),
)
class RecipeItemViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = RecipeItem.objects.select_related('product__restaurant', 'ingredient').all()
    serializer_class = RecipeItemSerializer
    # Filter via product → restaurant
    restaurant_filter_field = 'product__restaurant_id'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.get_requested_restaurant_id()
        if restaurant_id:
            queryset = queryset.filter(product__restaurant_id=restaurant_id)
        return queryset


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List products',
        description='Return menu products for the accessible restaurant(s).',
        responses={200: ProductSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get product details',
        responses={200: ProductSerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create product',
        request=ProductSerializer,
        responses={201: ProductSerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update product',
        request=ProductSerializer,
        responses={200: ProductSerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update product',
        request=ProductSerializer,
        responses={200: ProductSerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete product',
        responses={204: None},
    ),
)
class ProductViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
    queryset = (
        Product.objects.select_related('restaurant', 'category')
        .prefetch_related(
            Prefetch('recipe_items', queryset=RecipeItem.objects.select_related('ingredient'))
        )
        .all()
    )
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    restaurant_filter_field = 'restaurant_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.get_requested_restaurant_id()
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if restaurant:
            self.assert_restaurant_access(restaurant.id)
        serializer.save()
