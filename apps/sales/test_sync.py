from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Ingredient
from apps.restaurants.models import Restaurant
from apps.pos_lightspeed.services import LightspeedSalesSyncService
from apps.recipes.models import Category, Product, RecipeItem
from apps.sales.models import DailySalesRecord


class SalesSyncDetailedTests(TestCase):
    def setUp(self):
        self.restaurant_a = Restaurant.objects.create(name='Restaurant A', code='REST_A')
        self.restaurant_b = Restaurant.objects.create(name='Restaurant B', code='REST_B')

        self.category_a = Category.objects.create(restaurant=self.restaurant_a, name='Mains')
        self.category_b = Category.objects.create(restaurant=self.restaurant_b, name='Mains')

        self.ingredient_a = Ingredient.objects.create(
            restaurant=self.restaurant_a,
            name='Salmon',
            base_unit='kg',
            cost_per_base_unit=Decimal('20.00'),
        )

        self.product_a = Product.objects.create(
            restaurant=self.restaurant_a,
            category=self.category_a,
            name='Salmon Fillet',
            selling_price=Decimal('30.00'),
            lightspeed_item_id='ls_salmon_101',
        )
        RecipeItem.objects.create(
            product=self.product_a,
            ingredient=self.ingredient_a,
            quantity=Decimal('0.200'),
            unit='kg',
        )

        # Product with same name at restaurant B
        self.product_b = Product.objects.create(
            restaurant=self.restaurant_b,
            category=self.category_b,
            name='Salmon Fillet',
            selling_price=Decimal('35.00'),
            lightspeed_item_id='ls_salmon_202',
        )

    def test_sync_skips_unmapped_products(self):
        result = LightspeedSalesSyncService.sync_sales(
            restaurant=self.restaurant_a,
            sales_date='2026-09-09',
            items=[
                {
                    'product_name': 'Unknown Mystery Item',
                    'quantity': 5,
                    'unit_price': '10.00',
                },
                {
                    'product_name': 'Salmon Fillet',
                    'quantity': 3,
                    'unit_price': '30.00',
                },
            ],
        )

        self.assertEqual(result['total_revenue'], Decimal('90.00'))
        daily = DailySalesRecord.objects.get(restaurant=self.restaurant_a, date='2026-09-09')
        self.assertEqual(daily.sold_dishes.count(), 1)
        self.assertEqual(daily.sold_dishes.first().quantity_sold, 3)

    def test_sync_enforces_restaurant_isolation(self):
        # Sync at restaurant A using lightspeed_item_id of restaurant B
        result = LightspeedSalesSyncService.sync_sales(
            restaurant=self.restaurant_a,
            sales_date='2026-09-09',
            items=[
                {
                    'product_id': 'ls_salmon_202',  # Belongs to restaurant B!
                    'product_name': 'Different Name',
                    'quantity': 2,
                    'unit_price': '35.00',
                },
            ],
        )
        # Should NOT match product_b because restaurant does not match
        self.assertEqual(result['total_revenue'], Decimal('0.00'))

    def test_cumulative_sales_aggregation(self):
        # First sync
        LightspeedSalesSyncService.sync_sales(
            restaurant=self.restaurant_a,
            sales_date='2026-09-09',
            items=[
                {'product_name': 'Salmon Fillet', 'quantity': 2, 'unit_price': '30.00'},
            ],
        )
        # Second sync on same day
        result = LightspeedSalesSyncService.sync_sales(
            restaurant=self.restaurant_a,
            sales_date='2026-09-09',
            items=[
                {'product_name': 'Salmon Fillet', 'quantity': 3, 'unit_price': '30.00'},
            ],
        )
        self.assertEqual(result['total_revenue'], Decimal('150.00'))
        daily = DailySalesRecord.objects.get(restaurant=self.restaurant_a, date='2026-09-09')
        self.assertEqual(daily.sold_dishes.first().quantity_sold, 5)
