import uuid

from django.db import models

from apps.locations.models import Location


class LightspeedConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.OneToOneField(Location, on_delete=models.CASCADE, related_name='lightspeed_config')
    api_url = models.URLField(default='https://api.lightspeed.app')
    client_id = models.CharField(max_length=255, blank=True, default='')
    client_secret = models.CharField(max_length=255, blank=True, default='')
    access_token = models.TextField(blank=True, default='')
    refresh_token = models.TextField(blank=True, default='')
    token_expires_at = models.DateTimeField(null=True, blank=True)
    account_id = models.CharField(max_length=200, blank=True, default='')
    auto_sync_enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.location.name} Lightspeed'
