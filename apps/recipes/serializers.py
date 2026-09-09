from rest_framework import serializers

from .models import Category, Product, RecipeItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'location', 'name', 'color', 'sort_order']
        read_only_fields = ['id']


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
            'location',
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
