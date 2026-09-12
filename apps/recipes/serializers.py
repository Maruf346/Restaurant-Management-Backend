"""
apps/recipes/serializers.py
────────────────────────────
All serializers for the recipes app.

Key design decisions
────────────────────
• ProductSerializer accepts a writable `recipe_items` list so the frontend can
  create / replace all ingredients in a single request.
• Each item in `recipe_items` carries:
    - ingredient   (UUID)
    - quantity     (decimal)
    - unit         (UnitChoices value)
  The serializer calculates and returns `calculated_cost` per item and
  `total_cost` (alias `food_cost`) at the product level.
• On PUT/PATCH the existing recipe items are fully replaced by the submitted
  list (if the list is present in the payload).
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Category, Product, RecipeItem, RecentUpdate


# ---------------------------------------------------------------------------
# RecipeItem serializers
# ---------------------------------------------------------------------------

class RecipeItemReadSerializer(serializers.ModelSerializer):
    """Read-only representation of a single recipe ingredient row."""
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    base_unit = serializers.CharField(source='ingredient.base_unit', read_only=True)
    cost_per_base_unit = serializers.DecimalField(
        source='ingredient.cost_per_base_unit',
        max_digits=12,
        decimal_places=4,
        read_only=True,
    )
    calculated_cost = serializers.SerializerMethodField()

    class Meta:
        model = RecipeItem
        fields = [
            'id',
            'ingredient',
            'ingredient_name',
            'quantity',
            'unit',
            'base_unit',
            'cost_per_base_unit',
            'calculated_cost',
            'created_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=4))
    def get_calculated_cost(self, obj):
        """quantity × cost_per_base_unit (with unit conversion)."""
        return obj.ingredient_cost()


class RecipeItemWriteSerializer(serializers.Serializer):
    """
    Flat write payload for a single ingredient row inside a product.
    Used only for the nested `recipe_items` list on ProductSerializer.
    """
    ingredient = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    unit = serializers.ChoiceField(choices=[
        ('g', 'Gram (g)'),
        ('kg', 'Kilogram (kg)'),
        ('ml', 'Milliliter (ml)'),
        ('l', 'Liter (L)'),
        ('pcs', 'Pieces (pcs)'),
        ('pack', 'Pack'),
        ('dozen', 'Dozen'),
    ])


# Standalone endpoint serializer (for /api/recipes/items/)
class RecipeItemSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    calculated_cost = serializers.SerializerMethodField()

    class Meta:
        model = RecipeItem
        fields = [
            'id',
            'product',
            'ingredient',
            'ingredient_name',
            'quantity',
            'unit',
            'calculated_cost',
            'created_at',
        ]
        read_only_fields = ['id', 'ingredient_name', 'calculated_cost', 'created_at']

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=4))
    def get_calculated_cost(self, obj):
        return obj.ingredient_cost()


# ---------------------------------------------------------------------------
# Category serializers
# ---------------------------------------------------------------------------

class CategoryProductSerializer(serializers.ModelSerializer):
    """Compact product representation nested inside a category list."""
    picture = serializers.SerializerMethodField()
    thumbnail_color = serializers.CharField(read_only=True)
    no_of_ingredients = serializers.IntegerField(read_only=True)
    food_cost = serializers.DecimalField(source='recipe_cost', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'picture',
            'thumbnail_color',
            'no_of_ingredients',
            'food_cost',
            'selling_price',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'lightspeed_item_id',
            'is_active',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_picture(self, obj):
        if not obj.picture:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.picture.url)
        return obj.picture.url


class CategorySerializer(serializers.ModelSerializer):
    products = CategoryProductSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'restaurant', 'name', 'color', 'sort_order', 'products']
        read_only_fields = ['id', 'products']

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)
        if 'location' in data and 'restaurant' not in data:
            data['restaurant'] = data.pop('location')
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['location'] = ret.get('restaurant')
        return ret


class CategoryPerformanceSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the category performance endpoint."""
    avg_margin_pct = serializers.SerializerMethodField()
    avg_food_cost_pct = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'color', 'avg_margin_pct', 'avg_food_cost_pct', 'total_products']

    @extend_schema_field(serializers.FloatField())
    def get_avg_margin_pct(self, obj):
        val = obj.avg_margin_percentage()
        return round(float(val), 1)

    @extend_schema_field(serializers.FloatField())
    def get_avg_food_cost_pct(self, obj):
        val = obj.avg_food_cost_percentage()
        return round(float(val), 1)

    @extend_schema_field(serializers.IntegerField())
    def get_total_products(self, obj):
        return sum(1 for p in obj.products.all() if p.is_active)


# ---------------------------------------------------------------------------
# Product serializer (with writable nested recipe_items)
# ---------------------------------------------------------------------------

class ProductSerializer(serializers.ModelSerializer):
    """
    Full product serializer.

    Write (POST / PUT / PATCH)
    ──────────────────────────
    `recipe_items` is an optional list of ingredient rows. When supplied, the
    existing recipe items for the product are fully replaced. When omitted on
    a PATCH, existing items are left untouched.

    Example payload:
    ```json
    {
      "restaurant": "<uuid>",
      "category": "<uuid>",
      "name": "Pad Thai",
      "selling_price": "12.50",
      "thumbnail_color": "#f59e0b",
      "recipe_items": [
        {"ingredient": "<uuid>", "quantity": "200", "unit": "g"},
        {"ingredient": "<uuid>", "quantity": "0.5",  "unit": "l"}
      ]
    }
    ```

    Read (GET)
    ──────────
    Returns the full ingredient list with `calculated_cost` per row and a
    top-level `food_cost` / `total_cost` / `gross_profit` / `margin_percentage`.
    """

    # Writable nested ingredient list
    recipe_items = RecipeItemWriteSerializer(many=True, required=False, write_only=False)

    # Rich read-only output for recipe items
    recipe_items_detail = RecipeItemReadSerializer(
        source='recipe_items',
        many=True,
        read_only=True,
    )

    picture = serializers.ImageField(required=False, allow_null=True)
    no_of_ingredients = serializers.IntegerField(read_only=True)
    food_cost = serializers.DecimalField(
        source='recipe_cost', max_digits=12, decimal_places=2, read_only=True,
        help_text='Total ingredient cost (sum of each ingredient quantity × cost_per_base_unit).',
    )
    total_cost = serializers.DecimalField(
        source='recipe_cost', max_digits=12, decimal_places=2, read_only=True,
        help_text='Alias of food_cost.',
    )
    gross_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    food_cost_percentage = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    margin_percentage = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'restaurant',
            'category',
            'name',
            'selling_price',
            'thumbnail_color',
            'is_active',
            'picture',
            'lightspeed_item_id',
            'description',
            'no_of_ingredients',
            'food_cost',
            'total_cost',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'recipe_items',
            'recipe_items_detail',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'no_of_ingredients',
            'food_cost',
            'total_cost',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'recipe_items_detail',
            'created_at',
            'updated_at',
        ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_recipe_items(self, items):
        """Ensure no duplicate ingredients within a single product."""
        seen = set()
        for item in items:
            iid = item['ingredient']
            if iid in seen:
                raise serializers.ValidationError(
                    f"Ingredient {iid} appears more than once. Each ingredient must be unique per product."
                )
            seen.add(iid)
        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _replace_recipe_items(self, product, items_data):
        """
        Delete all existing RecipeItem rows for *product* and recreate them
        from *items_data*, adjusting ingredient stock for each change.

        Stock logic (must be inside an atomic block):
          • Each removed item  → restore its base qty back to ingredient stock
          • Each added item    → deduct its base qty from ingredient stock
        """
        from apps.inventory.models import Ingredient
        from apps.inventory.services import adjust_stock_for_recipe_item, convert_units

        # --- 1. Restore stock for all items being removed ---
        for old_item in product.recipe_items.select_related('ingredient').all():
            old_base_qty = convert_units(
                old_item.quantity,
                from_unit=old_item.unit,
                to_unit=old_item.ingredient.base_unit,
            )
            # Negative delta → restore stock (undo the previous deduction)
            adjust_stock_for_recipe_item(old_item.ingredient_id, -old_base_qty)

        product.recipe_items.all().delete()

        # --- 2. Deduct stock for all newly assigned items ---
        for item in items_data:
            ingredient = Ingredient.objects.get(
                id=item['ingredient'],
                restaurant=product.restaurant,
            )
            new_base_qty = convert_units(
                item['quantity'],
                from_unit=item['unit'],
                to_unit=ingredient.base_unit,
            )
            # Positive delta → deduct stock (recipe consumes ingredient)
            adjust_stock_for_recipe_item(ingredient.id, new_base_qty)

            RecipeItem.objects.create(
                product=product,
                ingredient=ingredient,
                quantity=item['quantity'],
                unit=item['unit'],
            )

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        recipe_items_data = validated_data.pop('recipe_items', [])
        product = super().create(validated_data)
        if recipe_items_data:
            self._replace_recipe_items(product, recipe_items_data)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        recipe_items_data = validated_data.pop('recipe_items', None)
        product = super().update(instance, validated_data)
        if recipe_items_data is not None:
            # Only replace when the key was explicitly provided
            self._replace_recipe_items(product, recipe_items_data)
        return product

    # ------------------------------------------------------------------
    # Serialization tweaks
    # ------------------------------------------------------------------

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)
        if 'location' in data and 'restaurant' not in data:
            data['restaurant'] = data.pop('location')
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['location'] = ret.get('restaurant')

        # Resolve picture to an absolute URL
        request = self.context.get('request')
        if instance.picture:
            ret['picture'] = (
                request.build_absolute_uri(instance.picture.url) if request
                else instance.picture.url
            )
        else:
            ret['picture'] = None

        # Keep recipe_items as the detailed representation on reads
        # (the write-only RecipeItemWriteSerializer data is replaced by the rich read view)
        ret['recipe_items'] = ret.pop('recipe_items_detail', [])
        return ret


# ---------------------------------------------------------------------------
# Recent Updates
# ---------------------------------------------------------------------------

def _time_ago(dt):
    """Return a human-readable relative time string."""
    now = timezone.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return 'Just now'
    if seconds < 3600:
        mins = seconds // 60
        return f'{mins} minute{"s" if mins != 1 else ""} ago'
    if seconds < 86400:
        hours = seconds // 3600
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    if seconds < 86400 * 2:
        return 'Yesterday'
    days = seconds // 86400
    if days < 7:
        return f'{days} days ago'
    weeks = days // 7
    if weeks < 4:
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    return dt.strftime('%d %b %Y')


class RecentUpdateSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = RecentUpdate
        fields = [
            'id',
            'update_type',
            'title',
            'description',
            'actor_name',
            'actor_role',
            'metadata',
            'time_ago',
            'created_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_time_ago(self, obj):
        return _time_ago(obj.created_at)
