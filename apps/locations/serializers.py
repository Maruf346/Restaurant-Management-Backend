from rest_framework import serializers

from .models import Location, UserLocation


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            'id', 'name', 'code', 'address', 'city', 'country',
            'currency', 'timezone', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserLocationSerializer(serializers.ModelSerializer):
    """Serializer for the UserLocation through-model (used in admin / Super Admin APIs)."""

    class Meta:
        model = UserLocation
        fields = ['id', 'user', 'location', 'assigned_at', 'assigned_by']
        read_only_fields = ['id', 'assigned_at']
