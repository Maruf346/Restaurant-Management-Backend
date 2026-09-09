from rest_framework import serializers

from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'code', 'address', 'city', 'country', 'currency', 'timezone', 'is_active']
        read_only_fields = fields
