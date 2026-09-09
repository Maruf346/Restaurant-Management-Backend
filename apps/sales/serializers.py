from rest_framework import serializers

from .models import DailySalesRecord, SoldDishRecord


class SoldDishRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoldDishRecord
        fields = [
            'id',
            'daily_sales',
            'product',
            'quantity_sold',
            'unit_selling_price',
            'total_sales',
            'theoretical_cost',
            'gross_profit',
            'margin_pct',
            'created_at',
        ]
        read_only_fields = ['id', 'total_sales', 'theoretical_cost', 'gross_profit', 'margin_pct', 'created_at']


class DailySalesRecordSerializer(serializers.ModelSerializer):
    sold_dishes = SoldDishRecordSerializer(many=True, read_only=True)

    class Meta:
        model = DailySalesRecord
        fields = [
            'id',
            'location',
            'date',
            'total_revenue',
            'total_cost',
            'gross_profit',
            'food_cost_pct',
            'profit_margin_pct',
            'sold_dishes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'total_revenue', 'total_cost', 'gross_profit', 'food_cost_pct', 'profit_margin_pct', 'created_at', 'updated_at']
