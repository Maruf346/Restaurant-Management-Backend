from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.inventory.models import Ingredient
from apps.locations.models import Location
from apps.users.models import User


class IngredientApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='inventory@example.com',
            username='inventory',
            password='StrongPass123',
            full_name='Inventory User',
            is_staff=True,
        )
        self.location = Location.objects.create(name='Downtown', code='DT5', currency='USD')
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'inventory@example.com', 'password': 'StrongPass123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    def test_ingredient_listing_and_creation(self):
        list_response = self.client.get(reverse('ingredients-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            reverse('ingredients-list'),
            {
                'location': str(self.location.id),
                'name': 'Onion',
                'base_unit': 'kg',
                'current_stock': '5.000',
                'min_stock_alert': '1.000',
                'cost_per_base_unit': '1.50',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Ingredient.objects.filter(name='Onion', location=self.location).exists())
