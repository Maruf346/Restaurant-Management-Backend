from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Location
from apps.pos_lightspeed.models import LightspeedConfig
from apps.users.models import User


class LightspeedConfigApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='lightspeed@example.com',
            username='lightspeed-user',
            password='StrongPass123',
            full_name='Lightspeed User',
            is_staff=True,
        )
        self.location = Location.objects.create(name='Downtown', code='DT5', currency='USD')
        LightspeedConfig.objects.create(
            location=self.location,
            client_id='client-123',
            client_secret='secret-456',
            account_id='acct-789',
            auto_sync_enabled=True,
        )

        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'lightspeed@example.com', 'password': 'StrongPass123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    def test_lightspeed_config_listing_returns_data(self):
        response = self.client.get(reverse('lightspeed-config-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['account_id'], 'acct-789')
