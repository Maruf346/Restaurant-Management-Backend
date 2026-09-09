"""
apps/pos_lightspeed/serializers.py
───────────────────────────────────
Safe serializers for Lightspeed POS integration.

CRITICAL SECURITY RULE:
  access_token and refresh_token MUST NEVER be exposed in any API serializer.
  Client credentials are kept in environment variables.
"""

from rest_framework import serializers

from .models import LightspeedConfig, LightspeedConnectionStatus


class LightspeedStatusSerializer(serializers.ModelSerializer):
    """
    Safe read-only serializer returned by the status and connect/disconnect endpoints.
    Exposes zero secret credentials.
    """
    connected = serializers.SerializerMethodField()
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = LightspeedConfig
        fields = [
            'id',
            'location',
            'location_name',
            'status',
            'connected',
            'requires_reauthorization',
            'auto_sync_enabled',
            'account_id',
            'business_location_id',
            'last_synced_at',
            'last_error',
            'last_error_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_connected(self, obj) -> bool:
        return obj.status == LightspeedConnectionStatus.CONNECTED


class LightspeedAuthorizeUrlSerializer(serializers.Serializer):
    """Response serializer returning the OAuth authorization URL to redirect to."""
    authorization_url = serializers.URLField()
    state = serializers.CharField()


class LightspeedManualSyncSerializer(serializers.Serializer):
    """Payload for triggering a manual sales sync."""
    date = serializers.DateField(
        required=False,
        help_text="Date to sync in YYYY-MM-DD format. Defaults to yesterday if omitted.",
    )


class LightspeedTokenSerializer(serializers.ModelSerializer):
    """
    INTERNAL USE ONLY: used by background tasks and services.
    NEVER expose this serializer in an API view or Swagger response.
    """
    class Meta:
        model = LightspeedConfig
        fields = ['access_token', 'refresh_token', 'token_expires_at']
