"""
apps/pos_lightspeed/oauth.py
────────────────────────────
Lightspeed OAuth 2.0 service.

Handles:
  - Building authorization URLs for initiating OAuth handshake
  - Exchanging authorization codes for access and refresh tokens
  - Refreshing expired access tokens using the refresh token
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
import requests

from .models import LightspeedAppCredential, POSProvider

logger = logging.getLogger(__name__)


class LightspeedOAuthError(Exception):
    """Raised when an OAuth communication or token exchange fails."""
    def __init__(self, message: str, status_code: int = None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class LightspeedOAuthService:
    """
    Encapsulates interaction with Lightspeed OAuth 2.0 endpoints for K-Series and L-Series.
    Fetches credentials dynamically from the admin-configured LightspeedAppCredential model,
    with fallback to settings.py for backward compatibility and test environments.
    """

    @classmethod
    def get_credential_config(cls, series: str = POSProvider.LIGHTSPEED_K) -> dict:
        """
        Retrieves credentials and endpoints for the specified series.
        First checks database (LightspeedAppCredential), then falls back to settings.
        """
        # 1. Try fetching from database model (admin-configured)
        try:
            cred = LightspeedAppCredential.objects.filter(series=series, is_active=True).first()
            if cred and cred.client_id and cred.client_secret:
                return {
                    'client_id': cred.client_id,
                    'client_secret': cred.client_secret,
                    'redirect_uri': cred.redirect_uri,
                    'auth_url': cred.auth_url,
                    'token_url': cred.token_url,
                    'scope': cred.scope or 'employee:all',
                }
        except Exception as exc:
            logger.warning("Could not query LightspeedAppCredential for %s: %s", series, exc)

        # 2. Fallback to settings.py for backward compatibility
        prefix = 'LIGHTSPEED_L_' if series == POSProvider.LIGHTSPEED_L else 'LIGHTSPEED_'
        client_id = getattr(settings, f'{prefix}CLIENT_ID', '') or getattr(settings, 'LIGHTSPEED_CLIENT_ID', '')
        client_secret = getattr(settings, f'{prefix}CLIENT_SECRET', '') or getattr(settings, 'LIGHTSPEED_CLIENT_SECRET', '')
        redirect_uri = getattr(settings, f'{prefix}REDIRECT_URI', '') or getattr(settings, 'LIGHTSPEED_REDIRECT_URI', '')
        auth_url = getattr(settings, f'{prefix}AUTH_URL', '') or getattr(settings, 'LIGHTSPEED_AUTH_URL', 'https://cloud.lightspeedapp.com/oauth/authorize.php')
        token_url = getattr(settings, f'{prefix}TOKEN_URL', '') or getattr(settings, 'LIGHTSPEED_TOKEN_URL', 'https://cloud.lightspeedapp.com/oauth/access_token.php')
        scope = getattr(settings, f'{prefix}SCOPE', '') or getattr(settings, 'LIGHTSPEED_SCOPE', 'employee:all')

        return {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'auth_url': auth_url,
            'token_url': token_url,
            'scope': scope,
        }

    @classmethod
    def get_client_id(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('client_id', '')

    @classmethod
    def get_client_secret(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('client_secret', '')

    @classmethod
    def get_redirect_uri(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('redirect_uri', '')

    @classmethod
    def get_auth_url(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('auth_url', '')

    @classmethod
    def get_token_url(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('token_url', '')

    @classmethod
    def get_scope(cls, series: str = POSProvider.LIGHTSPEED_K) -> str:
        return cls.get_credential_config(series).get('scope', 'employee:all')

    @classmethod
    def build_authorization_url(cls, state: str, series: str = POSProvider.LIGHTSPEED_K) -> str:
        """
        Build the Lightspeed OAuth 2.0 authorization URL for the requested series.
        """
        client_id = cls.get_client_id(series)
        redirect_uri = cls.get_redirect_uri(series)
        auth_url = cls.get_auth_url(series)
        scope = cls.get_scope(series)

        if not client_id or not redirect_uri:
            raise LightspeedOAuthError(
                f"OAuth credentials for {series} must be configured in Django Admin (LightspeedAppCredential) or settings."
            )

        params = {
            'response_type': 'code',
            'client_id': client_id,
            'scope': scope,
            'state': state,
            'redirect_uri': redirect_uri,
        }
        return f"{auth_url}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_tokens(cls, code: str, series: str = POSProvider.LIGHTSPEED_K) -> dict:
        """
        Exchange an authorization code for access and refresh tokens for the given series.
        """
        client_id = cls.get_client_id(series)
        client_secret = cls.get_client_secret(series)
        redirect_uri = cls.get_redirect_uri(series)
        token_url = cls.get_token_url(series)

        if not client_id or not client_secret:
            raise LightspeedOAuthError(
                f"OAuth credentials for {series} must be configured in Django Admin or settings."
            )

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }

        try:
            response = requests.post(token_url, data=payload, timeout=15)
        except requests.RequestException as exc:
            logger.error("Network error during Lightspeed (%s) code exchange: %s", series, exc)
            raise LightspeedOAuthError(f"Network error contacting Lightspeed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "Lightspeed (%s) token exchange failed: HTTP %s — %s",
                series,
                response.status_code,
                response.text,
            )
            raise LightspeedOAuthError(
                f"Failed to exchange code: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise LightspeedOAuthError("Lightspeed returned non-JSON token response") from exc

    @classmethod
    def refresh_access_token(cls, refresh_token: str, series: str = POSProvider.LIGHTSPEED_K) -> dict:
        """
        Refresh an expired access token using the stored refresh token for the given series.
        """
        client_id = cls.get_client_id(series)
        client_secret = cls.get_client_secret(series)
        token_url = cls.get_token_url(series)

        if not client_id or not client_secret:
            raise LightspeedOAuthError(f"OAuth credentials for {series} missing in Django Admin or settings.")

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }

        try:
            response = requests.post(token_url, data=payload, timeout=15)
        except requests.RequestException as exc:
            logger.error("Network error during Lightspeed (%s) token refresh: %s", series, exc)
            raise LightspeedOAuthError(f"Network error contacting Lightspeed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "Lightspeed (%s) token refresh failed: HTTP %s — %s",
                series,
                response.status_code,
                response.text,
            )
            raise LightspeedOAuthError(
                f"Failed to refresh access token: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise LightspeedOAuthError("Lightspeed returned non-JSON refresh response") from exc
