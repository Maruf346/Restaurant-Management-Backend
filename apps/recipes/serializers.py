from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Category, Product, RecipeItem, RecentUpdate


class CategoryProductSerializer(serializers.ModelSerializer):
    picture = serializers.SerializerMethodField()
    no_of_ingredients = serializers.IntegerField(read_only=True)
    food_cost = serializers.DecimalField(source='recipe_cost', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'picture',
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


class RecipeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeItem
        fields = ['id', 'product', 'ingredient', 'quantity', 'unit', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    recipe_items = RecipeItemSerializer(many=True, read_only=True)
    picture = serializers.ImageField(required=False, allow_null=True)
    no_of_ingredients = serializers.IntegerField(read_only=True)
    food_cost = serializers.DecimalField(source='recipe_cost', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'restaurant',
            'category',
            'name',
            'selling_price',
            'is_active',
            'picture',
            'lightspeed_item_id',
            'description',
            'no_of_ingredients',
            'food_cost',
            'recipe_cost',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'recipe_items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'no_of_ingredients',
            'food_cost',
            'recipe_cost',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'created_at',
            'updated_at',
        ]

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
        request = self.context.get('request')
        if instance.picture:
            if request:
                ret['picture'] = request.build_absolute_uri(instance.picture.url)
            else:
                ret['picture'] = instance.picture.url
        else:
            ret['picture'] = None
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
