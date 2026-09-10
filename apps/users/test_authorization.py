from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.restaurants.models import Restaurant, UserRestaurant
from apps.users.models import User, UserRole


class AuthorizationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_superuser(
            email='super@profitplate.com',
            username='superadmin',
            password='SuperPassword123!',
            role=UserRole.SUPER_ADMIN,
        )

        self.restaurant_admin = User.objects.create_user(
            email='admin1@restaurant.com',
            username='admin1',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )

        self.restaurant_a = Restaurant.objects.create(name='Restaurant A', code='REST_A')
        self.restaurant_b = Restaurant.objects.create(name='Restaurant B', code='REST_B')

        # Assign restaurant_admin to restaurant_a only
        UserRestaurant.objects.create(user=self.restaurant_admin, restaurant=self.restaurant_a)

    def test_super_admin_creates_restaurant_admin_with_restaurant_ids(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'new.manager@bistro.com',
                'full_name': 'New Manager',
                'password': 'InitialSecret123!',
                'restaurant_ids': [str(self.restaurant_b.id)],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'new.manager@bistro.com')
        self.assertTrue(response.data['password_change_required'])

        new_user = User.objects.get(email='new.manager@bistro.com')
        self.assertEqual(new_user.role, UserRole.RESTAURANT_ADMIN)
        self.assertTrue(new_user.assigned_restaurants.filter(id=self.restaurant_b.id).exists())

    def test_super_admin_creates_restaurant_admin_with_legacy_location_ids(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'legacy.manager@bistro.com',
                'full_name': 'Legacy Manager',
                'password': 'InitialSecret123!',
                'location_ids': [str(self.restaurant_b.id)],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'legacy.manager@bistro.com')

    def test_restaurant_admin_cannot_create_restaurant_admin(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'unauthorized@bistro.com',
                'full_name': 'Unauthorized',
                'password': 'InitialSecret123!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_sees_all_restaurants(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(reverse('restaurants:restaurant-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        ids = [item['id'] for item in results]
        self.assertIn(str(self.restaurant_a.id), ids)
        self.assertIn(str(self.restaurant_b.id), ids)

    def test_restaurant_admin_only_sees_assigned_restaurant(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(reverse('restaurants:restaurant-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        ids = [item['id'] for item in results]
        self.assertIn(str(self.restaurant_a.id), ids)
        self.assertNotIn(str(self.restaurant_b.id), ids)

    def test_restaurant_admin_cannot_access_unassigned_restaurant_detail(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(reverse('restaurants:restaurant-detail', args=[self.restaurant_b.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
