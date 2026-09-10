from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.restaurants.models import Restaurant, UserRestaurant
from apps.users.models import User, UserRole


class UserAuthTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser(
            email='super@profitplate.com',
            username='superadmin',
            password='SuperPassword123!',
            full_name='Super Administrator',
            role=UserRole.SUPER_ADMIN,
        )
        self.restaurant_admin = User.objects.create_user(
            email='admin@bistro.com',
            username='bistroadmin',
            password='TempPassword123!',
            full_name='Bistro Admin',
            role=UserRole.RESTAURANT_ADMIN,
            password_change_required=True,
        )

    def test_super_admin_login_success(self):
        response = self.client.post(
            reverse('auth:login'),
            {'email': 'super@profitplate.com', 'password': 'SuperPassword123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['role'], UserRole.SUPER_ADMIN)
        self.assertFalse(response.data['password_change_required'])
        # Profile picture field should be present in login response
        self.assertIn('profile_picture', response.data['user'])

    def test_restaurant_admin_login_requires_password_change(self):
        response = self.client.post(
            reverse('auth:login'),
            {'email': 'admin@bistro.com', 'password': 'TempPassword123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['role'], UserRole.RESTAURANT_ADMIN)
        self.assertTrue(response.data['password_change_required'])

    def test_login_invalid_credentials_returns_401(self):
        response = self.client.post(
            reverse('auth:login'),
            {'email': 'super@profitplate.com', 'password': 'WrongPassword'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user_returns_401(self):
        self.restaurant_admin.is_active = False
        self.restaurant_admin.save()

        response = self.client.post(
            reverse('auth:login'),
            {'email': 'admin@bistro.com', 'password': 'TempPassword123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        refresh = RefreshToken.for_user(self.super_admin)
        response = self.client.post(
            reverse('auth:refresh'),
            {'refresh': str(refresh)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_logout_blacklists_token(self):
        refresh = RefreshToken.for_user(self.super_admin)
        self.client.force_authenticate(user=self.super_admin)

        response = self.client.post(
            reverse('auth:logout'),
            {'refresh': str(refresh)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Trying to refresh with blacklisted token should fail
        refresh_response = self.client.post(
            reverse('auth:refresh'),
            {'refresh': str(refresh)},
            format='json',
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_clears_flag(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:change-password'),
            {
                'current_password': 'TempPassword123!',
                'new_password': 'BrandNewSecurePassword456!',
                'confirm_new_password': 'BrandNewSecurePassword456!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.restaurant_admin.refresh_from_db()
        self.assertFalse(self.restaurant_admin.password_change_required)
        self.assertTrue(self.restaurant_admin.check_password('BrandNewSecurePassword456!'))

    def test_change_password_invalid_current_password(self):
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:change-password'),
            {
                'current_password': 'IncorrectPassword!',
                'new_password': 'BrandNewSecurePassword456!',
                'confirm_new_password': 'BrandNewSecurePassword456!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_mismatched_confirmation(self):
        """confirm_new_password not matching new_password must return 400."""
        self.client.force_authenticate(user=self.restaurant_admin)
        response = self.client.post(
            reverse('users:change-password'),
            {
                'current_password': 'TempPassword123!',
                'new_password': 'BrandNewSecurePassword456!',
                'confirm_new_password': 'DifferentPassword789!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_new_password', response.data)

    def test_me_endpoint_returns_user_profile(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(reverse('users:current-user'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'super@profitplate.com')
        self.assertEqual(response.data['role'], UserRole.SUPER_ADMIN)
        self.assertIn('profile_picture', response.data)
