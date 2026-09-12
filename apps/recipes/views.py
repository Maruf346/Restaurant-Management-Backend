"""
apps/recipes/views.py
──────────────────────
Recipe viewsets with restaurant-level access control.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.restaurants.mixins import RestaurantAccessMixin
from .models import Category, Product, RecipeItem, RecentUpdate, UpdateType
from .serializers import (
    CategoryPerformanceSerializer,
    CategorySerializer,
    ProductSerializer,
    RecipeItemSerializer,
    RecentUpdateSerializer,
)


# ---------------------------------------------------------------------------
# Helper: log a RecentUpdate event
# ---------------------------------------------------------------------------

def _log_update(*, restaurant, update_type, title, description='', actor_name='System', actor_role='', created_by=None, metadata=None):
    RecentUpdate.objects.create(
        restaurant=restaurant,
        update_type=update_type,
        title=title,
        description=description,
        actor_name=actor_name,
        actor_role=actor_role,
        created_by=created_by,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# CategoryViewSet
# ---------------------------------------------------------------------------

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

    @extend_schema(
        tags=['recipes'],
        summary='Category performance',
        description=(
            'Return average gross margin % and food cost % per category, '
            'calculated from the selling price and food cost of all active products.'
        ),
        responses={200: CategoryPerformanceSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """GET /api/recipes/categories/performance/"""
        qs = self.get_queryset()
        serializer = CategoryPerformanceSerializer(qs, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# RecipeItemViewSet
# ---------------------------------------------------------------------------

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

    def _log_recipe_update(self, product, old_cost):
        """Log a RECIPE_UPDATED event when an ingredient is added/changed."""
        new_cost = product.recipe_cost()
        if old_cost is None or old_cost == 0:
            description = f'Ingredient added. Food cost is now {new_cost}.'
        else:
            delta_pct = ((new_cost - old_cost) / old_cost * 100) if old_cost else Decimal('0')
            sign = '+' if delta_pct >= 0 else ''
            description = f'Cost {sign}{delta_pct:.1f}%.'

        actor = None
        actor_name = 'System'
        actor_role = ''
        request = self.request
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            actor = request.user
            actor_name = getattr(actor, 'get_full_name', lambda: '')() or str(actor)
            actor_role = getattr(actor, 'role', '') or ''

        _log_update(
            restaurant=product.restaurant,
            update_type=UpdateType.RECIPE_UPDATED,
            title=f'Recipe updated: {product.name}',
            description=description,
            actor_name=actor_name,
            actor_role=actor_role,
            created_by=actor,
            metadata={'old_food_cost': str(old_cost), 'new_food_cost': str(new_cost)},
        )

    def perform_create(self, serializer):
        from apps.inventory.services import adjust_stock_for_recipe_item, convert_units

        product = serializer.validated_data.get('product')
        old_cost = product.recipe_cost() if product else None

        with transaction.atomic():
            instance = serializer.save()
            # Deduct stock: new ingredient is now consumed by this recipe
            base_qty = convert_units(
                instance.quantity,
                from_unit=instance.unit,
                to_unit=instance.ingredient.base_unit,
            )
            adjust_stock_for_recipe_item(instance.ingredient_id, base_qty)

        if product:
            self._log_recipe_update(product, old_cost)

    def perform_update(self, serializer):
        from apps.inventory.services import adjust_stock_for_recipe_item, convert_units

        instance = serializer.instance
        product = instance.product
        old_cost = product.recipe_cost()

        with transaction.atomic():
            # Capture old values before overwrite
            old_base_qty = convert_units(
                instance.quantity,
                from_unit=instance.unit,
                to_unit=instance.ingredient.base_unit,
            )
            saved = serializer.save()
            new_base_qty = convert_units(
                saved.quantity,
                from_unit=saved.unit,
                to_unit=saved.ingredient.base_unit,
            )
            # Delta: net change in usage (positive = more consumed, negative = less)
            delta = new_base_qty - old_base_qty
            if delta != 0:
                adjust_stock_for_recipe_item(saved.ingredient_id, delta)

        self._log_recipe_update(product, old_cost)

    def perform_destroy(self, instance):
        from apps.inventory.services import adjust_stock_for_recipe_item, convert_units

        product = instance.product
        old_cost = product.recipe_cost()

        with transaction.atomic():
            # Restore stock: ingredient is no longer consumed by this recipe
            base_qty = convert_units(
                instance.quantity,
                from_unit=instance.unit,
                to_unit=instance.ingredient.base_unit,
            )
            instance.delete()
            adjust_stock_for_recipe_item(instance.ingredient_id, -base_qty)

        self._log_recipe_update(product, old_cost)


# ---------------------------------------------------------------------------
# ProductViewSet
# ---------------------------------------------------------------------------

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
        instance = serializer.save()

        # Determine actor info
        actor = None
        actor_name = 'System'
        actor_role = ''
        request = self.request
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            actor = request.user
            actor_name = getattr(actor, 'get_full_name', lambda: '')() or str(actor)
            actor_role = getattr(actor, 'role', '') or ''

        category_name = instance.category.name if instance.category else 'Uncategorized'
        _log_update(
            restaurant=instance.restaurant,
            update_type=UpdateType.PRODUCT_ADDED,
            title=f'New product added: {instance.name}',
            description=f'Added to {category_name} category.',
            actor_name=actor_name,
            actor_role=actor_role,
            created_by=actor,
            metadata={'product_id': str(instance.id), 'category': category_name},
        )


# ---------------------------------------------------------------------------
# RecentUpdateViewSet
# ---------------------------------------------------------------------------

@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List recent updates',
        description=(
            'Return the recent activity feed for the restaurant: '
            'recipe changes, cost alerts, and new products. '
            'Ordered newest-first. Supports optional `?limit=N` query param (default 20).'
        ),
        parameters=[
            OpenApiParameter(name='limit', description='Max number of updates to return (default 20).', required=False, type=int),
            OpenApiParameter(name='update_type', description='Filter by event type: recipe_updated | cost_alert | product_added.', required=False, type=str),
        ],
        responses={200: RecentUpdateSerializer(many=True)},
    ),
)
class RecentUpdateViewSet(RestaurantAccessMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for the activity/event feed.
    Events are auto-generated by the system; no manual creation endpoint is exposed.
    """
    queryset = RecentUpdate.objects.select_related('restaurant', 'created_by').all()
    serializer_class = RecentUpdateSerializer
    permission_classes = [IsAuthenticated]
    restaurant_filter_field = 'restaurant_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_restaurant(queryset)
        restaurant_id = self.get_requested_restaurant_id()
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)

        # Optional filter by update_type
        update_type = self.request.query_params.get('update_type')
        if update_type:
            queryset = queryset.filter(update_type=update_type)

        # Limit (default 20)
        try:
            limit = int(self.request.query_params.get('limit', 20))
        except (TypeError, ValueError):
            limit = 20
        return queryset[:limit]
