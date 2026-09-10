from rest_framework import serializers

from apps.restaurants.models import Restaurant
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
    location = serializers.PrimaryKeyRelatedField(
        source='restaurant',
        queryset=Restaurant.objects.all(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = DailySalesRecord
        fields = [
            'id',
            'restaurant',
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

    def validate(self, attrs):
        if 'restaurant' not in attrs:
            raise serializers.ValidationError({'restaurant': ['This field is required.']})
        return attrs
