from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from django.conf import settings
import requests

from .models import LightspeedAppCredential, LightspeedConfig, POSProvider
from .token_refresh import LightspeedTokenRefreshService

logger = logging.getLogger(__name__)


class LightspeedApiError(Exception):
    """Raised on API errors returned by Lightspeed REST endpoints."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class BaseLightspeedApiClient(ABC):
    """
    Abstract base client for interacting with Lightspeed REST APIs.
    Provides automated token refresh, 401 retry, and common request infrastructure.
    """
    DEFAULT_BASE_URL = 'https://api.ikentoo.com'
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, config: LightspeedConfig):
        self.config = config

    @property
    def base_url(self) -> str:
        """
        Lookup API base URL from the database credential config, or fallback to settings/defaults.
        """
        try:
            cred = LightspeedAppCredential.objects.filter(
                series=self.config.series,
                is_active=True,
            ).first()
            if cred and cred.api_base_url:
                return cred.api_base_url
        except Exception:
            pass

        prefix = 'LIGHTSPEED_L_' if self.config.series == POSProvider.LIGHTSPEED_L else 'LIGHTSPEED_'
        return getattr(settings, f'{prefix}API_BASE_URL', getattr(settings, 'LIGHTSPEED_API_BASE_URL', self.DEFAULT_BASE_URL))

    def _ensure_valid_token(self) -> str:
        """
        Ensure access token is fresh. Refreshes if near expiry.
        Returns the valid access token.
        """
        self.config = LightspeedTokenRefreshService.refresh_if_needed(self.config)
        return self.config.access_token

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> Any:
        """
        Execute an authenticated HTTP request against Lightspeed API.
        If a 401 is encountered and retry_on_401 is True, force-refreshes the token and retries once.
        """
        token = self._ensure_valid_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        url = urljoin(self.base_url.rstrip('/') + '/', endpoint.lstrip('/'))

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=self.DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("HTTP request error contacting Lightspeed (%s): %s", url, exc)
            raise LightspeedApiError(f"Network error contacting Lightspeed: {exc}") from exc

        if response.status_code == 401 and retry_on_401:
            logger.warning("Received 401 from Lightspeed; forcing token refresh and retrying.")
            self.config = LightspeedTokenRefreshService.refresh_if_needed(self.config, force=True)
            return self._request(method, endpoint, params=params, data=data, retry_on_401=False)

        if not (200 <= response.status_code < 300):
            logger.error(
                "Lightspeed API error: HTTP %s on %s — %s",
                response.status_code,
                url,
                response.text,
            )
            raise LightspeedApiError(
                f"Lightspeed API returned status {response.status_code}",
                status_code=response.status_code,
                response_text=response.text,
            )

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise LightspeedApiError("Failed to decode JSON response from Lightspeed") from exc

    @abstractmethod
    def get_orders(self, date_from: str, date_to: str, **kwargs) -> List[Dict[str, Any]]:
        """Fetch finalized orders between date_from and date_to (inclusive)."""
        pass

    @abstractmethod
    def get_products(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch catalog products/menu items for mapping."""
        pass


class KSeriesApiClient(BaseLightspeedApiClient):
    """
    Client for interacting with the Lightspeed K-Series (iKentoo) REST API.
    """
    DEFAULT_BASE_URL = 'https://api.ikentoo.com'

    def get_orders(self, date_from: str, date_to: str, **kwargs) -> List[Dict[str, Any]]:
        params = {
            'date_from': date_from,
            'date_to': date_to,
        }
        if self.config.business_location_id:
            params['business_location_id'] = self.config.business_location_id
        params.update(kwargs)

        result = self._request('GET', '/v1/orders', params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'orders' in result:
            return result['orders']
        return []

    def get_products(self, **kwargs) -> List[Dict[str, Any]]:
        params = {}
        if self.config.business_location_id:
            params['business_location_id'] = self.config.business_location_id
        params.update(kwargs)

        result = self._request('GET', '/v1/products', params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'products' in result:
            return result['products']
        return []


class LSeriesApiClient(BaseLightspeedApiClient):
    """
    Client for interacting with the Lightspeed L-Series (Restaurant POS / Hospitality) REST API.
    """
    DEFAULT_BASE_URL = 'https://api.lightspeedhq.com'

    def get_orders(self, date_from: str, date_to: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch orders for Lightspeed L-Series.
        """
        params = {
            'startDate': date_from,
            'endDate': date_to,
        }
        if self.config.business_location_id:
            params['locationId'] = self.config.business_location_id
        params.update(kwargs)

        # L-Series endpoints can be customized or pointed to specific paths
        result = self._request('GET', '/v1/orders', params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'orders' in result:
            return result['orders']
        return []

    def get_products(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch menu items/products for Lightspeed L-Series.
        """
        params = {}
        if self.config.business_location_id:
            params['locationId'] = self.config.business_location_id
        params.update(kwargs)

        result = self._request('GET', '/v1/products', params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'products' in result:
            return result['products']
        return []


def get_lightspeed_client(config: LightspeedConfig) -> BaseLightspeedApiClient:
    """
    Factory function to instantiate the appropriate API client based on config.series.
    """
    if config.series == POSProvider.LIGHTSPEED_L:
        return LSeriesApiClient(config)
    return KSeriesApiClient(config)


# Backward compatibility alias
class LightspeedApiClient:
    """
    Backwards-compatible wrapper delegating to the appropriate series client.
    """
    def __new__(cls, config: LightspeedConfig):
        return get_lightspeed_client(config)
