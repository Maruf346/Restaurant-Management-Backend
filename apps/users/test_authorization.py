from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Location, UserLocation
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
            email='admin1@location.com',
            username='admin1',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )

        self.location_a = Location.objects.create(name='Location A', code='LOC_A')
        self.location_b = Location.objects.create(name='Location B', code='LOC_B')

        # Assign restaurant_admin to location_a only
        UserLocation.objects.create(user=self.restaurant_admin, location=self.location_a)

    def test_super_admin_creates_restaurant_admin(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'new.manager@bistro.com',
                'full_name': 'New Manager',
                'password': 'InitialSecret123!',
                'location_ids': [str(self.location_b.id)],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'new.manager@bistro.com')
        self.assertTrue(response.data['password_change_required'])

        new_user = User.objects.get(email='new.manager@bistro.com')
        self.assertEqual(new_user.role, UserRole.RESTAURANT_ADMIN)
        self.assertTrue(new_user.assigned_locations.filter(id=self.location_b.id).exists())

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

    def test_super_admin_sees_all_locations(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(reverse('locations:location-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DRF pagination returns 'results'
        results = response.data.get('results', response.data)
        ids = [item['id'] for item in results]
        self.assertIn(str(self.location_a.id), ids)
        self.assertIn(str(self.location_b.id), ids)

    def test_restaurant_admin_only_sees_assigned_location(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(reverse('locations:location-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        ids = [item['id'] for item in results]
        self.assertIn(str(self.location_a.id), ids)
        self.assertNotIn(str(self.location_b.id), ids)

    def test_restaurant_admin_cannot_access_unassigned_location_detail(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(reverse('locations:location-detail', args=[self.location_b.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
