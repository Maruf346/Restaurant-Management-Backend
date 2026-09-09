"""
apps/pos_lightspeed/models.py
──────────────────────────────
LightspeedConfig — stores the OAuth connection between a restaurant Location
and the Lightspeed K-Series API.

SECURITY NOTES:
  - access_token and refresh_token are sensitive credentials. They MUST NOT
    be returned through normal API serializers.
  - client_id and client_secret are application-level credentials. They are
    stored in environment variables (LIGHTSPEED_CLIENT_ID / LIGHTSPEED_CLIENT_SECRET),
    NOT in this model.
  - The only fields the frontend should ever see are the safe status fields
    (status, connected, requires_reauthorization, etc.).
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.locations.models import Location


class LightspeedConnectionStatus(models.TextChoices):
    CONNECTED = 'CONNECTED', 'Connected'
    REAUTH_REQUIRED = 'REAUTH_REQUIRED', 'Reauthorization Required'
    DISCONNECTED = 'DISCONNECTED', 'Disconnected'
    ERROR = 'ERROR', 'Error'


class LightspeedConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.OneToOneField(
        Location,
        on_delete=models.CASCADE,
        related_name='lightspeed_config',
    )

    # ── Connection status ──────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=LightspeedConnectionStatus.choices,
        default=LightspeedConnectionStatus.DISCONNECTED,
        db_index=True,
    )
    requires_reauthorization = models.BooleanField(default=False)

    # ── OAuth tokens (INTERNAL — never expose via API) ─────────────────────
    access_token = models.TextField(blank=True, default='')
    refresh_token = models.TextField(blank=True, default='')
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # ── Lightspeed account identifiers ────────────────────────────────────
    account_id = models.CharField(max_length=200, blank=True, default='')
    business_location_id = models.CharField(max_length=200, blank=True, default='')

    # ── Sync settings ─────────────────────────────────────────────────────
    auto_sync_enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    # ── Error tracking ────────────────────────────────────────────────────
    last_error = models.TextField(blank=True, default='')
    last_error_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lightspeed Configuration'
        verbose_name_plural = 'Lightspeed Configurations'

    def __str__(self):
        return f'{self.location.name} — Lightspeed ({self.status})'

    # ── Status helpers ─────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self.status == LightspeedConnectionStatus.CONNECTED

    def is_token_near_expiry(self, buffer_seconds: int = 300) -> bool:
        """
        Return True if the access token will expire within buffer_seconds.
        Returns True if token_expires_at is not set (treat as expired).
        """
        if not self.token_expires_at:
            return True
        remaining = (self.token_expires_at - timezone.now()).total_seconds()
        return remaining < buffer_seconds

    # ── State transitions ──────────────────────────────────────────────────

    def mark_connected(
        self,
        access_token: str,
        refresh_token: str,
        expires_at,
        account_id: str = '',
        business_location_id: str = '',
    ) -> None:
        """
        Atomically save new tokens and mark the connection as CONNECTED.
        Always call this after a successful OAuth exchange or token refresh.
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = expires_at
        self.status = LightspeedConnectionStatus.CONNECTED
        self.requires_reauthorization = False
        self.last_error = ''
        if account_id:
            self.account_id = account_id
        if business_location_id:
            self.business_location_id = business_location_id
        self.save(update_fields=[
            'access_token', 'refresh_token', 'token_expires_at',
            'status', 'requires_reauthorization', 'last_error',
            'account_id', 'business_location_id', 'updated_at',
        ])

    def mark_reauth_required(self, error_message: str = '') -> None:
        """
        Called when a token refresh fails permanently.
        Clears stored tokens and sets status to REAUTH_REQUIRED so the
        frontend can prompt the user to reconnect.
        """
        self.status = LightspeedConnectionStatus.REAUTH_REQUIRED
        self.requires_reauthorization = True
        self.access_token = ''
        self.refresh_token = ''
        self.token_expires_at = None
        if error_message:
            self.last_error = error_message
            self.last_error_at = timezone.now()
        self.save(update_fields=[
            'status', 'requires_reauthorization',
            'access_token', 'refresh_token', 'token_expires_at',
            'last_error', 'last_error_at', 'updated_at',
        ])

    def mark_disconnected(self) -> None:
        """
        Called on a deliberate disconnect action from the UI.
        Clears stored tokens and resets status.
        """
        self.status = LightspeedConnectionStatus.DISCONNECTED
        self.requires_reauthorization = False
        self.access_token = ''
        self.refresh_token = ''
        self.token_expires_at = None
        self.save(update_fields=[
            'status', 'requires_reauthorization',
            'access_token', 'refresh_token', 'token_expires_at', 'updated_at',
        ])

    def record_error(self, error_message: str) -> None:
        self.last_error = error_message
        self.last_error_at = timezone.now()
        self.save(update_fields=['last_error', 'last_error_at', 'updated_at'])

    @property
    def redis_lock_key(self) -> str:
        """Redis key used to prevent concurrent token refresh operations."""
        return f'lightspeed_token_refresh_lock:{self.id}'

    @property
    def token_refresh_lock_key(self) -> str:
        return self.redis_lock_key
