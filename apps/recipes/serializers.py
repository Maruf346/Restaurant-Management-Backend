from rest_framework import serializers

from .models import Category, Product, RecipeItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'restaurant', 'name', 'color', 'sort_order']
        read_only_fields = ['id']

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

    class Meta:
        model = Product
        fields = [
            'id',
            'restaurant',
            'category',
            'name',
            'selling_price',
            'is_active',
            'lightspeed_item_id',
            'description',
            'recipe_cost',
            'gross_profit',
            'food_cost_percentage',
            'margin_percentage',
            'recipe_items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'recipe_cost', 'gross_profit', 'food_cost_percentage', 'margin_percentage', 'created_at', 'updated_at']

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
