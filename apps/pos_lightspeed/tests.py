from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.restaurants.models import Restaurant, UserRestaurant
from apps.pos_lightspeed.models import LightspeedConfig, LightspeedConnectionStatus
from apps.pos_lightspeed.state import OAuthStateManager
from apps.users.models import User, UserRole


class LightspeedApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_superuser(
            email='super@profitplate.com',
            username='superadmin',
            password='SuperPassword123!',
            role=UserRole.SUPER_ADMIN,
        )

        self.restaurant_admin = User.objects.create_user(
            email='admin@bistro.com',
            username='admin_bistro',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )

        self.other_admin = User.objects.create_user(
            email='other@bistro.com',
            username='admin_other',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )

        self.restaurant = Restaurant.objects.create(name='Downtown Bistro', code='DT_BISTRO')
        UserRestaurant.objects.create(user=self.restaurant_admin, restaurant=self.restaurant)

        self.config = LightspeedConfig.objects.create(
            restaurant=self.restaurant,
            status=LightspeedConnectionStatus.CONNECTED,
            access_token='super_secret_access_token_123',
            refresh_token='super_secret_refresh_token_456',
            account_id='acc_9999',
            business_location_id='biz_loc_8888',
        )

    def test_status_endpoint_never_exposes_tokens(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(
            reverse('pos_lightspeed:status'),
            {'restaurant_id': str(self.restaurant.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # CRITICAL SECURITY TEST: Ensure sensitive token fields are completely absent
        data_str = str(response.data)
        self.assertNotIn('super_secret_access_token_123', data_str)
        self.assertNotIn('super_secret_refresh_token_456', data_str)
        self.assertNotIn('access_token', response.data)
        self.assertNotIn('refresh_token', response.data)
        self.assertEqual(response.data['status'], LightspeedConnectionStatus.CONNECTED)
        self.assertTrue(response.data['connected'])

    def test_restaurant_admin_can_view_assigned_restaurant_status(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(
            reverse('pos_lightspeed:status'),
            {'restaurant_id': str(self.restaurant.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unassigned_admin_cannot_view_status(self):
        self.client.force_authenticate(user=self.other_admin)
        response = self.client.get(
            reverse('pos_lightspeed:status'),
            {'restaurant_id': str(self.restaurant.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.pos_lightspeed.oauth.LightspeedOAuthService.get_client_id', return_value='test_client')
    @patch('apps.pos_lightspeed.oauth.LightspeedOAuthService.get_redirect_uri', return_value='https://test.com/cb')
    def test_authorize_endpoint_generates_url_and_state(self, mock_uri, mock_id):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(
            reverse('pos_lightspeed:authorize'),
            {'restaurant_id': str(self.restaurant.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('authorization_url', response.data)
        self.assertIn('state', response.data)

        # Check state is valid in cache
        state = response.data['state']
        payload = OAuthStateManager.validate_and_consume_state(state)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['restaurant_id'], str(self.restaurant.id))

    def test_callback_with_invalid_state_fails(self):
        response = self.client.get(
            reverse('pos_lightspeed:callback'),
            {'code': 'valid_code', 'state': 'invalid_state'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.pos_lightspeed.oauth.LightspeedOAuthService.exchange_code_for_tokens')
    def test_callback_success_connects_restaurant(self, mock_exchange):
        mock_exchange.return_value = {
            'access_token': 'new_access_token_abc',
            'refresh_token': 'new_refresh_token_xyz',
            'expires_in': 3600,
            'account_id': 'acc_123',
        }
        state = OAuthStateManager.create_state(self.super_admin.id, restaurant_id=self.restaurant.id)

        response = self.client.get(
            reverse('pos_lightspeed:callback'),
            {'code': 'test_auth_code', 'state': state},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.config.refresh_from_db()
        self.assertEqual(self.config.status, LightspeedConnectionStatus.CONNECTED)
        self.assertEqual(self.config.access_token, 'new_access_token_abc')
        self.assertEqual(self.config.account_id, 'acc_123')

        # Replay attempt with consumed state must fail
        replay_response = self.client.get(
            reverse('pos_lightspeed:callback'),
            {'code': 'test_auth_code', 'state': state},
        )
        self.assertEqual(replay_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disconnect_clears_tokens(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('pos_lightspeed:disconnect'),
            {'restaurant_id': str(self.restaurant.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.config.refresh_from_db()
        self.assertEqual(self.config.status, LightspeedConnectionStatus.DISCONNECTED)
        self.assertEqual(self.config.access_token, '')
        self.assertEqual(self.config.refresh_token, '')
        self.assertIsNone(self.config.token_expires_at)
