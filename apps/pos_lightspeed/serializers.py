from rest_framework import serializers

from .models import LightspeedConfig


class LightspeedConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = LightspeedConfig
        fields = [
            'id',
            'location',
            'api_url',
            'client_id',
            'client_secret',
            'access_token',
            'refresh_token',
            'token_expires_at',
            'account_id',
            'auto_sync_enabled',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_synced_at']
