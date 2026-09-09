from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Location
from apps.users.models import User


class UserAuthApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='StrongPass123',
            full_name='Admin User',
            is_staff=True,
        )

    def test_register_user_creates_account(self):
        response = self.client.post(
            reverse('register-user'),
            {
                'email': 'new.user@example.com',
                'username': 'newuser',
                'password': 'StrongPass123',
                'full_name': 'New User',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new.user@example.com').exists())

    def test_me_endpoint_returns_authenticated_user(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'admin@example.com', 'password': 'StrongPass123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'admin@example.com')


class LocationApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='manager@example.com',
            username='manager',
            password='StrongPass123',
            full_name='Manager User',
            is_staff=True,
        )
        self.location = Location.objects.create(name='Downtown', code='DT4', currency='USD')
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'manager@example.com', 'password': 'StrongPass123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    def test_locations_listing_returns_data(self):
        response = self.client.get(reverse('locations-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
