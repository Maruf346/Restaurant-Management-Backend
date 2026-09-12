from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.inventory.models import Ingredient
from apps.recipes.models import Category, Product, RecipeItem
from apps.restaurants.models import Restaurant, UserRestaurant
from apps.users.models import User


class InventoryAndRecipeCalculationTests(APITestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            name='Downtown',
            code='DT1',
            currency='USD',
        )
        self.ingredient = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Tomato',
            base_unit='kg',
            current_stock=Decimal('3.000'),
            cost_per_base_unit=Decimal('2.50'),
            latest_purchase_price=Decimal('2.50'),
            min_stock_alert=Decimal('1.000'),
        )
        self.category = Category.objects.create(restaurant=self.restaurant, name='Mains')
        self.product = Product.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name='Tomato Pasta',
            selling_price=Decimal('20.00'),
        )
        self.recipe_item = RecipeItem.objects.create(
            product=self.product,
            ingredient=self.ingredient,
            quantity=Decimal('0.500'),
            unit='kg',
        )

    def test_ingredient_purchase_updates_stock_and_cost(self):
        self.ingredient.apply_purchase(quantity=Decimal('2.000'), unit='kg', purchase_price=Decimal('8.00'))

        self.assertEqual(self.ingredient.current_stock, Decimal('5.000'))
        self.assertEqual(self.ingredient.cost_per_base_unit, Decimal('4.00'))
        self.assertEqual(self.ingredient.latest_purchase_price, Decimal('8.00'))

    def test_recipe_item_cost_is_based_on_base_unit_conversion(self):
        self.assertEqual(self.recipe_item.ingredient_cost(), Decimal('1.25'))

    def test_product_recipe_cost_and_food_cost_percentage(self):
        self.assertEqual(self.product.recipe_cost(), Decimal('1.25'))
        self.assertEqual(self.product.food_cost_percentage(), Decimal('6.25'))

    def test_product_margin_is_calculated_for_pricing(self):
        self.assertEqual(self.product.gross_profit(), Decimal('18.75'))
        self.assertEqual(self.product.margin_percentage(), Decimal('93.75'))


class CategoryAndProductApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='chef@restaurant.com',
            username='chef',
            password='StrongPassword123',
            full_name='Head Chef',
            is_staff=True,
        )
        self.restaurant = Restaurant.objects.create(name='Bistro Central', code='BC1', currency='USD')
        UserRestaurant.objects.create(user=self.user, restaurant=self.restaurant)

        login_res = self.client.post(
            reverse('auth:login'),
            {'email': 'chef@restaurant.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")

        # Setup Category
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name='Burgers',
            color='#3b82f6',
            sort_order=1,
        )

        # Setup 2 Ingredients
        self.beef = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Beef Patty',
            base_unit='g',
            current_stock=Decimal('10000'),
            cost_per_base_unit=Decimal('0.02'),  # $20 / kg = $0.02 / g
        )
        self.bun = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='Brioche Bun',
            base_unit='pcs',
            current_stock=Decimal('100'),
            cost_per_base_unit=Decimal('0.50'),  # $0.50 per bun
        )

        # Setup Product with 2 ingredients
        self.product = Product.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name='Cheeseburger Deluxe',
            selling_price=Decimal('12.00'),
            lightspeed_item_id='LS-BURGER-01',
        )
        # 150g beef patty = 150 * 0.02 = $3.00
        RecipeItem.objects.create(
            product=self.product,
            ingredient=self.beef,
            quantity=Decimal('150'),
            unit='g',
        )
        # 1 bun = 1 * 0.50 = $0.50
        # Total food cost = $3.50
        RecipeItem.objects.create(
            product=self.product,
            ingredient=self.bun,
            quantity=Decimal('1'),
            unit='pcs',
        )

    def test_categories_list_includes_nested_products_with_food_cost_and_ingredient_count(self):
        url = reverse('categories-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)

        category_data = results[0]
        self.assertEqual(category_data['name'], 'Burgers')
        self.assertIn('products', category_data)
        self.assertEqual(len(category_data['products']), 1)

        prod_data = category_data['products'][0]
        self.assertEqual(prod_data['name'], 'Cheeseburger Deluxe')
        self.assertEqual(prod_data['no_of_ingredients'], 2)
        # Total cost: 150g * 0.02 ($3.00) + 1 * 0.50 ($0.50) = 3.50
        self.assertEqual(Decimal(str(prod_data['food_cost'])), Decimal('3.50'))
        self.assertEqual(Decimal(str(prod_data['selling_price'])), Decimal('12.00'))
        self.assertEqual(Decimal(str(prod_data['gross_profit'])), Decimal('8.50'))
        self.assertEqual(prod_data['lightspeed_item_id'], 'LS-BURGER-01')
        self.assertIsNone(prod_data['picture'])
