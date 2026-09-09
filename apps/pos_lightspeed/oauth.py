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

logger = logging.getLogger(__name__)


class LightspeedOAuthError(Exception):
    """Raised when an OAuth communication or token exchange fails."""
    def __init__(self, message: str, status_code: int = None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class LightspeedOAuthService:
    """
    Encapsulates all interaction with Lightspeed OAuth 2.0 endpoints.
    """

    @classmethod
    def get_client_id(cls) -> str:
        return getattr(settings, 'LIGHTSPEED_CLIENT_ID', '') or ''

    @classmethod
    def get_client_secret(cls) -> str:
        return getattr(settings, 'LIGHTSPEED_CLIENT_SECRET', '') or ''

    @classmethod
    def get_redirect_uri(cls) -> str:
        return getattr(settings, 'LIGHTSPEED_REDIRECT_URI', '') or ''

    @classmethod
    def get_auth_url(cls) -> str:
        return getattr(
            settings,
            'LIGHTSPEED_AUTH_URL',
            'https://cloud.lightspeedapp.com/oauth/authorize.php',
        )

    @classmethod
    def get_token_url(cls) -> str:
        return getattr(
            settings,
            'LIGHTSPEED_TOKEN_URL',
            'https://cloud.lightspeedapp.com/oauth/access_token.php',
        )

    @classmethod
    def get_scope(cls) -> str:
        return getattr(settings, 'LIGHTSPEED_SCOPE', 'employee:all')

    @classmethod
    def build_authorization_url(cls, state: str) -> str:
        """
        Build the Lightspeed OAuth 2.0 authorization URL to which the user
        must be redirected.
        """
        client_id = cls.get_client_id()
        redirect_uri = cls.get_redirect_uri()
        if not client_id or not redirect_uri:
            raise LightspeedOAuthError(
                "LIGHTSPEED_CLIENT_ID and LIGHTSPEED_REDIRECT_URI must be configured in settings."
            )

        params = {
            'response_type': 'code',
            'client_id': client_id,
            'scope': cls.get_scope(),
            'state': state,
            'redirect_uri': redirect_uri,
        }
        return f"{cls.get_auth_url()}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_tokens(cls, code: str) -> dict:
        """
        Exchange an authorization code for access and refresh tokens.

        Returns:
            dict containing:
                access_token: str
                refresh_token: str
                expires_in: int (seconds)
                token_type: str
                account_id: optional str
        """
        client_id = cls.get_client_id()
        client_secret = cls.get_client_secret()
        redirect_uri = cls.get_redirect_uri()

        if not client_id or not client_secret:
            raise LightspeedOAuthError(
                "LIGHTSPEED_CLIENT_ID and LIGHTSPEED_CLIENT_SECRET must be configured."
            )

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }

        try:
            response = requests.post(cls.get_token_url(), data=payload, timeout=15)
        except requests.RequestException as exc:
            logger.error("Network error during Lightspeed code exchange: %s", exc)
            raise LightspeedOAuthError(f"Network error contacting Lightspeed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "Lightspeed token exchange failed: HTTP %s — %s",
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
    def refresh_access_token(cls, refresh_token: str) -> dict:
        """
        Refresh an expired access token using the stored refresh token.

        Returns:
            dict containing:
                access_token: str
                refresh_token: str (new refresh token if rotated)
                expires_in: int
        """
        client_id = cls.get_client_id()
        client_secret = cls.get_client_secret()

        if not client_id or not client_secret:
            raise LightspeedOAuthError("Lightspeed credentials missing in settings.")

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }

        try:
            response = requests.post(cls.get_token_url(), data=payload, timeout=15)
        except requests.RequestException as exc:
            logger.error("Network error during Lightspeed token refresh: %s", exc)
            raise LightspeedOAuthError(f"Network error contacting Lightspeed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "Lightspeed token refresh failed: HTTP %s — %s",
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
