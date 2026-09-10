from rest_framework import serializers

from .models import Restaurant, UserRestaurant


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'code', 'address', 'city', 'country',
            'currency', 'timezone', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserRestaurantSerializer(serializers.ModelSerializer):
    """Serializer for the UserRestaurant through-model (used in admin / Super Admin APIs)."""

    class Meta:
        model = UserRestaurant
        fields = ['id', 'user', 'restaurant', 'assigned_at', 'assigned_by']
        read_only_fields = ['id', 'assigned_at']


# Backward-compatible aliases
LocationSerializer = RestaurantSerializer
UserLocationSerializer = UserRestaurantSerializer
