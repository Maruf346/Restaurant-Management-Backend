from rest_framework import serializers

from .models import Category, Product, RecipeItem


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
