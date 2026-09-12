from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Ingredient, PurchaseEntry
from .services import convert_units, record_purchase_entry, update_purchase_entry


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

    def validate_current_stock(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Current stock cannot be negative.')
        return value

    def validate_min_stock_alert(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Min stock alert cannot be negative.')
        return value

    def validate_latest_purchase_price(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Latest purchase price cannot be negative.')
        return value

    def validate_cost_per_base_unit(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Cost per base unit cannot be negative.')
        return value

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
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    base_unit = serializers.CharField(source='ingredient.base_unit', read_only=True)
    unit = serializers.CharField(max_length=20, required=False, allow_null=True, default=None)

    class Meta:
        model = PurchaseEntry
        fields = [
            'id',
            'restaurant',
            'ingredient',
            'ingredient_name',
            'base_unit',
            'supplier_name',
            'quantity',
            'unit',
            'purchase_price',
            'unit_cost',
            'purchase_date',
            'created_by',
            'created_at',
        ]
        read_only_fields = ['id', 'unit_cost', 'created_by', 'created_at', 'ingredient_name', 'base_unit']

    def validate_quantity(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError('Purchase quantity must be greater than zero.')
        return value

    def validate_purchase_price(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Purchase price cannot be negative.')
        return value

    def validate(self, attrs):
        restaurant = attrs.get('restaurant') or (self.instance.restaurant if self.instance else None)
        ingredient = attrs.get('ingredient') or (self.instance.ingredient if self.instance else None)
        unit = attrs.get('unit') or (self.instance.unit if self.instance else None)
        quantity = attrs.get('quantity') or (self.instance.quantity if self.instance else None)

        if restaurant and ingredient and ingredient.restaurant_id != restaurant.id:
            raise serializers.ValidationError({'ingredient': 'Selected ingredient does not belong to this restaurant.'})

        if not unit and ingredient:
            unit = ingredient.base_unit
            attrs['unit'] = unit

        if ingredient and unit:
            try:
                convert_units(quantity or Decimal('1'), from_unit=unit, to_unit=ingredient.base_unit)
            except (DjangoValidationError, Exception) as exc:
                message = getattr(exc, 'message', str(exc))
                if isinstance(exc, DjangoValidationError) and hasattr(exc, 'message_dict'):
                    message = exc.message_dict
                raise serializers.ValidationError({'unit': message})

        supplier_name = attrs.get('supplier_name')
        if not supplier_name and ingredient and ingredient.supplier_name:
            attrs['supplier_name'] = ingredient.supplier_name

        return attrs

    def create(self, validated_data):
        ingredient = validated_data.pop('ingredient')
        restaurant = validated_data.pop('restaurant')
        created_by = validated_data.pop('created_by', None)
        try:
            return record_purchase_entry(
                restaurant=restaurant,
                ingredient_id=ingredient.id,
                quantity=validated_data.get('quantity'),
                unit=validated_data.get('unit'),
                purchase_price=validated_data.get('purchase_price'),
                purchase_date=validated_data.get('purchase_date'),
                supplier_name=validated_data.get('supplier_name', ''),
                created_by=created_by,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)

    def update(self, instance, validated_data):
        try:
            return update_purchase_entry(
                instance,
                quantity=validated_data.get('quantity'),
                unit=validated_data.get('unit'),
                purchase_price=validated_data.get('purchase_price'),
                purchase_date=validated_data.get('purchase_date'),
                supplier_name=validated_data.get('supplier_name'),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)

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
