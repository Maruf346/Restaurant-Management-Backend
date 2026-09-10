"""
apps/pos_lightspeed/state.py
────────────────────────────
Cryptographically secure OAuth state manager using Redis / Django Cache.

State prevents CSRF attacks during the OAuth 2.0 authorization code flow.
The state token binds the authorization request to the specific user and
restaurant that initiated it.
"""

import json
import secrets
from typing import Optional

from django.core.cache import cache


class OAuthStateManager:
    """
    Manages generation, storage, and one-time consumption of OAuth state tokens.
    """
    PREFIX = 'lightspeed_oauth_state:'
    TTL_SECONDS = 600  # 10 minutes

    @classmethod
    def _make_key(cls, state: str) -> str:
        return f"{cls.PREFIX}{state}"

    @classmethod
    def create_state(cls, user_id, restaurant_id=None, location_id=None) -> str:
        """
        Generate a cryptographically secure state token, associate it with
        the user_id and restaurant_id, and store it in Redis with an expiry.
        """
        target_id = restaurant_id or location_id
        state = secrets.token_urlsafe(32)
        payload = {
            'user_id': str(user_id),
            'restaurant_id': str(target_id),
            'location_id': str(target_id),
        }
        cache.set(cls._make_key(state), json.dumps(payload), timeout=cls.TTL_SECONDS)
        return state

    @classmethod
    def validate_and_consume_state(cls, state: str) -> Optional[dict]:
        """
        Validate that the state exists in cache, consume it (delete it to prevent
        replay attacks), and return the stored payload {user_id, restaurant_id, location_id}.
        Returns None if the state is invalid or expired.
        """
        if not state:
            return None

        key = cls._make_key(state)
        raw_val = cache.get(key)
        if not raw_val:
            return None

        # Delete immediately to ensure one-time usage
        cache.delete(key)

        try:
            payload = json.loads(raw_val)
            if 'restaurant_id' not in payload and 'location_id' in payload:
                payload['restaurant_id'] = payload['location_id']
            if 'location_id' not in payload and 'restaurant_id' in payload:
                payload['location_id'] = payload['restaurant_id']
            return payload
        except (json.JSONDecodeError, TypeError):
            return None
