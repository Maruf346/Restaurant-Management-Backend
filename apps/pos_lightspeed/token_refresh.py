"""
apps/pos_lightspeed/token_refresh.py
───────────────────────────────────
Token refresh service with distributed locking.

Prevents the "thundering herd" problem where multiple concurrent Celery
workers or API requests simultaneously try to refresh the same expired token.
"""

from datetime import timedelta
import logging
import time
from typing import Optional

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import LightspeedConfig, LightspeedConnectionStatus
from .oauth import LightspeedOAuthError, LightspeedOAuthService

logger = logging.getLogger(__name__)


class TokenRefreshLockError(Exception):
    """Raised when a distributed lock cannot be acquired."""
    pass


class LightspeedTokenRefreshService:
    """
    Handles safe token refreshes for Lightspeed configurations using
    distributed Redis locks and atomic database updates.
    """
    LOCK_TTL = 60  # seconds
    BUFFER_SECONDS = 300  # refresh if token expires within 5 minutes

    @classmethod
    def _acquire_lock(cls, config: LightspeedConfig) -> bool:
        """
        Attempt to acquire an exclusive lock using Redis cache.add (atomic SET NX).
        """
        key = config.token_refresh_lock_key
        # cache.add sets the key ONLY if it does not already exist
        return bool(cache.add(key, 'locked', timeout=cls.LOCK_TTL))

    @classmethod
    def _release_lock(cls, config: LightspeedConfig) -> None:
        """Release the distributed lock."""
        cache.delete(config.token_refresh_lock_key)

    @classmethod
    def refresh_if_needed(cls, config: LightspeedConfig, force: bool = False) -> LightspeedConfig:
        """
        Checks if the config's access token is expired or near expiry.
        If so, acquires a distributed lock and refreshes the token.
        If another worker is currently refreshing, it waits and re-reads
        the freshly updated config.
        """
        if not config.refresh_token:
            logger.warning("Config %s has no refresh_token; cannot refresh.", config.id)
            config.mark_reauth_required()
            return config

        if not force and not config.is_token_near_expiry(buffer_seconds=cls.BUFFER_SECONDS):
            return config

        # Attempt to acquire the distributed lock
        lock_acquired = cls._acquire_lock(config)

        if not lock_acquired:
            # Another process is refreshing the token. Wait up to 5 seconds and poll DB.
            logger.info("Token refresh lock active for config %s; waiting for update.", config.id)
            for _ in range(10):
                time.sleep(0.5)
                config.refresh_from_db()
                if not config.is_token_near_expiry(buffer_seconds=cls.BUFFER_SECONDS):
                    logger.info("Config %s token updated by concurrent worker.", config.id)
                    return config

            # If still expired after waiting, proceed to try acquiring lock once more
            lock_acquired = cls._acquire_lock(config)
            if not lock_acquired:
                raise TokenRefreshLockError(
                    f"Could not acquire token refresh lock for Lightspeed config {config.id}"
                )

        try:
            return cls._execute_refresh(config)
        finally:
            cls._release_lock(config)

    @classmethod
    def _execute_refresh(cls, config: LightspeedConfig) -> LightspeedConfig:
        """
        Executes the actual HTTP refresh request and saves new tokens atomically.
        """
        with transaction.atomic():
            # Lock the DB row to avoid race condition with other DB transactions
            config = LightspeedConfig.objects.select_for_update().get(pk=config.pk)

            # Re-check in case another transaction just finished
            if not config.is_token_near_expiry(buffer_seconds=cls.BUFFER_SECONDS):
                return config

            try:
                token_data = LightspeedOAuthService.refresh_access_token(config.refresh_token)
            except LightspeedOAuthError as exc:
                logger.error(
                    "Lightspeed refresh failed for config %s: %s (status: %s)",
                    config.id,
                    exc,
                    getattr(exc, 'status_code', None),
                )
                # If HTTP 400/401/403, refresh token is revoked or permanently invalid
                if getattr(exc, 'status_code', None) in (400, 401, 403):
                    config.mark_reauth_required()
                else:
                    config.mark_error(f"Refresh failed: {exc}")
                raise

            new_access_token = token_data.get('access_token', '')
            new_refresh_token = token_data.get('refresh_token') or config.refresh_token
            expires_in = int(token_data.get('expires_in', 3600))
            expires_at = timezone.now() + timedelta(seconds=expires_in)

            config.mark_connected(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_at=expires_at,
                account_id=config.account_id,
                business_location_id=config.business_location_id,
            )
            logger.info("Successfully refreshed Lightspeed token for config %s", config.id)
            return config
