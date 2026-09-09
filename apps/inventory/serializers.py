from rest_framework import serializers

from .models import Ingredient


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = [
            'id',
            'location',
            'name',
            'base_unit',
            'current_stock',
            'min_stock_alert',
            'latest_purchase_price',
            'cost_per_base_unit',
            'supplier_name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
