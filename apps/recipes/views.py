"""
apps/recipes/views.py
──────────────────────
Recipe viewsets with location-level access control.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.locations.mixins import LocationAccessMixin
from .models import Category, Product, RecipeItem
from .serializers import CategorySerializer, ProductSerializer, RecipeItemSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List categories',
        description='Return menu categories for the accessible location(s).',
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
class CategoryViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = Category.objects.select_related('location').all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_location(queryset)
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def perform_create(self, serializer):
        location = serializer.validated_data.get('location')
        if location:
            self.assert_location_access(location.id)
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
class RecipeItemViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = RecipeItem.objects.select_related('product__location', 'ingredient').all()
    serializer_class = RecipeItemSerializer
    # Filter via product → location
    location_filter_field = 'product__location_id'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset_by_location(queryset)


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List products',
        description='Return menu products for the accessible location(s).',
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
class ProductViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related('location', 'category').prefetch_related('recipe_items').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_location(queryset)
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def perform_create(self, serializer):
        location = serializer.validated_data.get('location')
        if location:
            self.assert_location_access(location.id)
        serializer.save()
