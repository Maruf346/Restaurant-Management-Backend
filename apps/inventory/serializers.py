from rest_framework import serializers

from .models import Ingredient, PurchaseEntry


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = [
            'id',
            'restaurant',
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


class PurchaseEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseEntry
        fields = [
            'id',
            'restaurant',
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
