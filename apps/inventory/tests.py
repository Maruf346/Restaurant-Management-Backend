from decimal import Decimal
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.inventory.models import Ingredient, PurchaseEntry, UnitChoices
from apps.inventory.services import convert_units
from apps.restaurants.models import Restaurant, UserRestaurant
from apps.users.models import User


class InventoryUnitConversionTests(APITestCase):
    def test_weight_conversions(self):
        # 2 kg -> 2000 g
        self.assertEqual(convert_units(2, UnitChoices.KILOGRAM, UnitChoices.GRAM), Decimal('2000'))
        # 500 g -> 0.5 kg
        self.assertEqual(convert_units(500, UnitChoices.GRAM, UnitChoices.KILOGRAM), Decimal('0.5'))

    def test_volume_conversions(self):
        # 1.5 l -> 1500 ml
        self.assertEqual(convert_units(Decimal('1.5'), UnitChoices.LITER, UnitChoices.MILLILITER), Decimal('1500'))
        # 250 ml -> 0.25 l
        self.assertEqual(convert_units(250, UnitChoices.MILLILITER, UnitChoices.LITER), Decimal('0.25'))

    def test_count_conversions(self):
        # 2 dozen -> 24 pcs
        self.assertEqual(convert_units(2, UnitChoices.DOZEN, UnitChoices.PIECE), Decimal('24'))
        # 12 pcs -> 1 dozen
        self.assertEqual(convert_units(12, UnitChoices.PIECE, UnitChoices.DOZEN), Decimal('1'))

    def test_incompatible_families_raise_validation_error(self):
        with self.assertRaises(ValidationError):
            convert_units(5, UnitChoices.LITER, UnitChoices.GRAM)
        with self.assertRaises(ValidationError):
            convert_units(1, UnitChoices.PIECE, UnitChoices.KILOGRAM)


class InventoryApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='inventory@example.com',
            username='inventory',
            password='StrongPass123',
            full_name='Inventory User',
            is_staff=True,
        )
        self.restaurant = Restaurant.objects.create(name='Downtown', code='DT5', currency='USD')
        UserRestaurant.objects.create(user=self.user, restaurant=self.restaurant)

        self.other_restaurant = Restaurant.objects.create(name='Uptown', code='UP2', currency='USD')

        token_response = self.client.post(
            reverse('auth:login'),
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
                'restaurant': str(self.restaurant.id),
                'name': 'Onion',
                'base_unit': 'kg',
                'current_stock': '5.000',
                'min_stock_alert': '1.000',
                'cost_per_base_unit': '1.50',
                'supplier_name': 'Default Farm',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Ingredient.objects.filter(name='Onion', restaurant=self.restaurant).exists())

    def test_purchase_entry_creation_updates_ingredient(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Chicken Breast',
            base_unit=UnitChoices.GRAM,
            current_stock=Decimal('0'),
            min_stock_alert=Decimal('500'),
            supplier_name='Default Supplier',
        )

        # Purchase 5 kg for $25.00 from Supplier A (5 kg = 5000 g, $25 / 5000g = 0.005 / g)
        purchase_data = {
            'restaurant': str(self.restaurant.id),
            'ingredient': str(ingredient.id),
            'supplier_name': 'Metro Supplier',
            'quantity': '5.000',
            'unit': 'kg',
            'purchase_price': '25.00',
            'purchase_date': '2026-09-12',
        }

        response = self.client.post(reverse('purchases-list'), purchase_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal('5000.000'))
        self.assertEqual(ingredient.latest_purchase_price, Decimal('25.00'))
        self.assertEqual(ingredient.cost_per_base_unit, Decimal('0.0050'))
        self.assertEqual(ingredient.supplier_name, 'Metro Supplier')

        purchase = PurchaseEntry.objects.get(id=response.data['id'])
        self.assertEqual(purchase.supplier_name, 'Metro Supplier')
        self.assertEqual(purchase.unit_cost, Decimal('5.0000'))  # $25 / 5 kg

    def test_multiple_purchases_preserve_supplier_snapshot(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Beef Mince',
            base_unit=UnitChoices.GRAM,
            current_stock=Decimal('0'),
        )

        # First purchase from Supplier 1
        res1 = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Prime Meats',
                'quantity': '2.000',
                'unit': 'kg',
                'purchase_price': '16.00',
                'purchase_date': '2026-09-01',
            },
            format='json',
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Second purchase from Supplier 2
        res2 = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Local Butcher',
                'quantity': '3.000',
                'unit': 'kg',
                'purchase_price': '27.00',
                'purchase_date': '2026-09-05',
            },
            format='json',
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        p1 = PurchaseEntry.objects.get(id=res1.data['id'])
        p2 = PurchaseEntry.objects.get(id=res2.data['id'])

        # Both purchases preserve their distinct supplier snapshot
        self.assertEqual(p1.supplier_name, 'Prime Meats')
        self.assertEqual(p2.supplier_name, 'Local Butcher')

        ingredient.refresh_from_db()
        # 2 kg + 3 kg = 5000 g
        self.assertEqual(ingredient.current_stock, Decimal('5000.000'))
        # Latest active supplier is Local Butcher
        self.assertEqual(ingredient.supplier_name, 'Local Butcher')
        self.assertEqual(ingredient.latest_purchase_price, Decimal('27.00'))
        self.assertEqual(ingredient.cost_per_base_unit, Decimal('0.0090'))  # $27 / 3000g

    def test_purchase_update_adjusts_stock_delta(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Flour',
            base_unit=UnitChoices.KILOGRAM,
            current_stock=Decimal('0'),
        )

        res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Bake Supplies',
                'quantity': '10.000',
                'unit': 'kg',
                'purchase_price': '30.00',
                'purchase_date': '2026-09-10',
            },
            format='json',
        )
        purchase_id = res.data['id']

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal('10.000'))

        # Update purchase from 10 kg to 15 kg for $45.00
        patch_res = self.client.patch(
            reverse('purchases-detail', kwargs={'pk': purchase_id}),
            {'quantity': '15.000', 'purchase_price': '45.00'},
            format='json',
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal('15.000'))
        self.assertEqual(ingredient.latest_purchase_price, Decimal('45.00'))
        self.assertEqual(ingredient.cost_per_base_unit, Decimal('3.0000'))

    def test_purchase_delete_rolls_back_stock(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Sugar',
            base_unit=UnitChoices.KILOGRAM,
            current_stock=Decimal('0'),
        )

        p1_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Sugar Corp',
                'quantity': '10.000',
                'unit': 'kg',
                'purchase_price': '20.00',
                'purchase_date': '2026-09-01',
            },
            format='json',
        )

        p2_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Sweet World',
                'quantity': '5.000',
                'unit': 'kg',
                'purchase_price': '15.00',
                'purchase_date': '2026-09-05',
            },
            format='json',
        )

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal('15.000'))

        # Delete purchase 2
        del_res = self.client.delete(reverse('purchases-detail', kwargs={'pk': p2_res.data['id']}))
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        ingredient.refresh_from_db()
        # Stock rolled back to 10 kg
        self.assertEqual(ingredient.current_stock, Decimal('10.000'))
        # Reverts to p1's price and supplier
        self.assertEqual(ingredient.latest_purchase_price, Decimal('20.00'))
        self.assertEqual(ingredient.supplier_name, 'Sugar Corp')
        self.assertEqual(ingredient.cost_per_base_unit, Decimal('2.0000'))

    def test_validation_errors(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Olive Oil',
            base_unit=UnitChoices.LITER,
            current_stock=Decimal('0'),
        )

        # Incompatible unit: buying kg for a liter ingredient
        bad_unit_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'quantity': '2.000',
                'unit': 'kg',
                'purchase_price': '20.00',
                'purchase_date': '2026-09-12',
            },
            format='json',
        )
        self.assertEqual(bad_unit_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unit', bad_unit_res.data)

        # Negative quantity
        neg_qty_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'quantity': '-5.000',
                'unit': 'l',
                'purchase_price': '20.00',
                'purchase_date': '2026-09-12',
            },
            format='json',
        )
        self.assertEqual(neg_qty_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Negative price
        neg_price_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'quantity': '5.000',
                'unit': 'l',
                'purchase_price': '-10.00',
                'purchase_date': '2026-09-12',
            },
            format='json',
        )
        self.assertEqual(neg_price_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Cross-restaurant mismatch
        other_ingredient = Ingredient.objects.create(
            restaurant=self.other_restaurant,
            name='Other Ingredient',
            base_unit=UnitChoices.GRAM,
        )
        mismatch_res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(other_ingredient.id),
                'quantity': '5.000',
                'unit': 'g',
                'purchase_price': '10.00',
                'purchase_date': '2026-09-12',
            },
            format='json',
        )
        self.assertEqual(mismatch_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_ingredient_purchase_history(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Coffee Beans',
            base_unit=UnitChoices.KILOGRAM,
            current_stock=Decimal('0'),
        )

        other_ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Tea Leaves',
            base_unit=UnitChoices.KILOGRAM,
            current_stock=Decimal('0'),
        )

        # 2 purchases for coffee
        self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Roaster A',
                'quantity': '10.000',
                'unit': 'kg',
                'purchase_price': '100.00',
                'purchase_date': '2026-09-01',
            },
            format='json',
        )
        self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Roaster B',
                'quantity': '5.000',
                'unit': 'kg',
                'purchase_price': '55.00',
                'purchase_date': '2026-09-05',
            },
            format='json',
        )

        # 1 purchase for tea
        self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(other_ingredient.id),
                'supplier_name': 'Tea Garden',
                'quantity': '2.000',
                'unit': 'kg',
                'purchase_price': '30.00',
                'purchase_date': '2026-09-02',
            },
            format='json',
        )

        # Test 1: Nested action endpoint GET /api/inventory/ingredients/{id}/purchases/
        history_url = reverse('ingredients-purchases', kwargs={'pk': str(ingredient.id)})
        res1 = self.client.get(history_url)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        results1 = res1.data.get('results', res1.data)
        self.assertEqual(len(results1), 2)
        # Most recent purchase first
        self.assertEqual(results1[0]['supplier_name'], 'Roaster B')
        self.assertEqual(results1[1]['supplier_name'], 'Roaster A')

        # Test 2: Query param filtering on GET /api/inventory/purchases/?ingredient={id}
        filter_url = f"{reverse('purchases-list')}?ingredient={ingredient.id}"
        res2 = self.client.get(filter_url)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        results2 = res2.data.get('results', res2.data)
        self.assertEqual(len(results2), 2)

    def test_purchase_omitted_unit_defaults_to_ingredient_base_unit(self):
        ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Butter',
            base_unit=UnitChoices.KILOGRAM,
            current_stock=Decimal('0'),
        )

        # Send purchase payload without "unit"
        res = self.client.post(
            reverse('purchases-list'),
            {
                'restaurant': str(self.restaurant.id),
                'ingredient': str(ingredient.id),
                'supplier_name': 'Dairy Farm',
                'quantity': '4.000',
                'purchase_price': '20.00',
                'purchase_date': '2026-09-12',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['unit'], 'kg')

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal('4.000'))
