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

    # ── Create Admin — Super Admin ────────────────────────────────────────

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

    # ── Create Admin — Restaurant Admin ──────────────────────────────────

    def test_restaurant_admin_can_create_admin_for_own_restaurant(self):
        """Restaurant Admin can invite a co-admin for their own restaurant."""
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'co.admin@bistro.com',
                'full_name': 'Co Admin',
                'password': 'InitialSecret123!',
                'restaurant_ids': [str(self.restaurant_a.id)],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(email='co.admin@bistro.com')
        self.assertTrue(new_user.assigned_restaurants.filter(id=self.restaurant_a.id).exists())

    def test_restaurant_admin_cannot_create_admin_for_unassigned_restaurant(self):
        """Restaurant Admin assigning restaurant they don't manage → 400 with clear message."""
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:restaurant-admins'),
            {
                'email': 'unauthorized@bistro.com',
                'full_name': 'Unauthorized',
                'password': 'InitialSecret123!',
                'restaurant_ids': [str(self.restaurant_b.id)],  # Not assigned to restaurant_b
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('restaurant_ids', response.data)
        # Error message should mention what went wrong
        error_msg = str(response.data['restaurant_ids'])
        self.assertIn('You can only assign', error_msg)

    # ── Restaurant listing ─────────────────────────────────────────────────

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

    # ── Admin list scoping ─────────────────────────────────────────────────

    def test_restaurant_admin_sees_only_co_admins(self):
        """Restaurant Admin can only see other admins sharing a restaurant."""
        # co_admin shares restaurant_a with restaurant_admin
        co_admin = User.objects.create_user(
            email='co@restaurant.com',
            username='coadmin',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )
        UserRestaurant.objects.create(user=co_admin, restaurant=self.restaurant_a)

        # other_admin is only on restaurant_b — should NOT appear
        other_admin = User.objects.create_user(
            email='other@restaurant.com',
            username='otheradmin',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )
        UserRestaurant.objects.create(user=other_admin, restaurant=self.restaurant_b)

        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.get(reverse('users:restaurant-admins'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        emails = [u['email'] for u in results]
        self.assertIn('co@restaurant.com', emails)
        self.assertNotIn('other@restaurant.com', emails)

    # ── Toggle status ──────────────────────────────────────────────────────

    def test_super_admin_can_toggle_restaurant_admin_status(self):
        self.client.force_authenticate(user=self.super_admin)
        # Initially active
        self.assertTrue(self.restaurant_admin.is_active)

        response = self.client.patch(
            reverse('users:toggle-restaurant-admin-status', args=[self.restaurant_admin.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.restaurant_admin.refresh_from_db()
        self.assertFalse(self.restaurant_admin.is_active)

        # Toggle back
        response = self.client.patch(
            reverse('users:toggle-restaurant-admin-status', args=[self.restaurant_admin.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.restaurant_admin.refresh_from_db()
        self.assertTrue(self.restaurant_admin.is_active)

    def test_restaurant_admin_can_toggle_co_admin_status(self):
        """Restaurant Admin can toggle status of a co-admin sharing their restaurant."""
        co_admin = User.objects.create_user(
            email='co2@restaurant.com',
            username='co2admin',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )
        UserRestaurant.objects.create(user=co_admin, restaurant=self.restaurant_a)

        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.patch(
            reverse('users:toggle-restaurant-admin-status', args=[co_admin.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        co_admin.refresh_from_db()
        self.assertFalse(co_admin.is_active)

    def test_restaurant_admin_cannot_toggle_unrelated_admin(self):
        """Restaurant Admin gets 403 when trying to toggle an admin from another restaurant."""
        other_admin = User.objects.create_user(
            email='other2@restaurant.com',
            username='other2admin',
            password='Password123!',
            role=UserRole.RESTAURANT_ADMIN,
        )
        UserRestaurant.objects.create(user=other_admin, restaurant=self.restaurant_b)

        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.patch(
            reverse('users:toggle-restaurant-admin-status', args=[other_admin.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', response.data)
