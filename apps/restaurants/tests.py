from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.restaurants.models import Restaurant, UserRestaurant
from apps.users.models import UserRole

User = get_user_model()


class RestaurantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser(
            email='superadmin@test.com',
            password='TestPassword123!',
        )
        self.restaurant_admin = User.objects.create_user(
            email='admin@bistro.com',
            password='TestPassword123!',
            role=UserRole.RESTAURANT_ADMIN,
        )
        self.restaurant_a = Restaurant.objects.create(
            name='Restaurant Alpha',
            code='REST_A',
            currency='USD',
        )
        self.restaurant_b = Restaurant.objects.create(
            name='Restaurant Beta',
            code='REST_B',
            currency='USD',
        )
        UserRestaurant.objects.create(
            user=self.restaurant_admin,
            restaurant=self.restaurant_a,
            assigned_by=self.super_admin,
        )

    def test_super_admin_can_list_all_restaurants(self):
        self.client.force_authenticate(user=self.super_admin)
        res = self.client.get('/api/restaurants/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should see both
        names = [r['name'] for r in res.data['results']] if 'results' in res.data else [r['name'] for r in res.data]
        self.assertIn('Restaurant Alpha', names)
        self.assertIn('Restaurant Beta', names)

    def test_restaurant_admin_only_sees_assigned_restaurants(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        res = self.client.get('/api/restaurants/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = [r['name'] for r in res.data['results']] if 'results' in res.data else [r['name'] for r in res.data]
        self.assertIn('Restaurant Alpha', names)
        self.assertNotIn('Restaurant Beta', names)

    def test_super_admin_can_create_restaurant(self):
        self.client.force_authenticate(user=self.super_admin)
        payload = {
            'name': 'Restaurant Gamma',
            'code': 'REST_G',
            'currency': 'USD',
            'timezone': 'UTC',
        }
        res = self.client.post('/api/restaurants/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'Restaurant Gamma')
        self.assertTrue(Restaurant.objects.filter(code='REST_G').exists())

    def test_restaurant_admin_cannot_create_restaurant(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        payload = {
            'name': 'Unauthorized Restaurant',
            'code': 'REST_UNAUTH',
        }
        res = self.client.post('/api/restaurants/', payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
