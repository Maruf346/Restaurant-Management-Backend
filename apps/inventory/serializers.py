from rest_framework import serializers

from .models import Ingredient, PurchaseEntry


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


class PurchaseEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseEntry
        fields = [
            'id',
            'location',
            'ingredient',
            'supplier_name',
            'quantity',
            'unit',
            'purchase_price',
            'unit_cost',
            'purchase_date',
            'created_by',
            'created_at',
        ]
        read_only_fields = ['id', 'unit_cost', 'created_by', 'created_at']
