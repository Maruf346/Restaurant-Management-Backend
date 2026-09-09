from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Ingredient
from apps.locations.models import Location
from apps.pos_lightspeed.services import LightspeedSalesSyncService
from apps.recipes.models import Category, Product, RecipeItem
from apps.sales.models import DailySalesRecord


class SalesSyncDetailedTests(TestCase):
    def setUp(self):
        self.location_a = Location.objects.create(name='Location A', code='LOC_A')
        self.location_b = Location.objects.create(name='Location B', code='LOC_B')

        self.category_a = Category.objects.create(location=self.location_a, name='Mains')
        self.category_b = Category.objects.create(location=self.location_b, name='Mains')

        self.ingredient_a = Ingredient.objects.create(
            location=self.location_a,
            name='Salmon',
            base_unit='kg',
            cost_per_base_unit=Decimal('20.00'),
        )

        self.product_a = Product.objects.create(
            location=self.location_a,
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

        # Product with same name at location B
        self.product_b = Product.objects.create(
            location=self.location_b,
            category=self.category_b,
            name='Salmon Fillet',
            selling_price=Decimal('35.00'),
            lightspeed_item_id='ls_salmon_202',
        )

    def test_sync_skips_unmapped_products(self):
        result = LightspeedSalesSyncService.sync_sales(
            location=self.location_a,
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
        daily = DailySalesRecord.objects.get(location=self.location_a, date='2026-09-09')
        self.assertEqual(daily.sold_dishes.count(), 1)
        self.assertEqual(daily.sold_dishes.first().quantity_sold, 3)

    def test_sync_enforces_location_isolation(self):
        # Sync at location A using lightspeed_item_id of location B
        result = LightspeedSalesSyncService.sync_sales(
            location=self.location_a,
            sales_date='2026-09-09',
            items=[
                {
                    'product_id': 'ls_salmon_202',  # Belongs to location B!
                    'product_name': 'Different Name',
                    'quantity': 2,
                    'unit_price': '35.00',
                },
            ],
        )
        # Should NOT match product_b because location does not match
        self.assertEqual(result['total_revenue'], Decimal('0.00'))

    def test_cumulative_sales_aggregation(self):
        # First sync
        LightspeedSalesSyncService.sync_sales(
            location=self.location_a,
            sales_date='2026-09-09',
            items=[
                {'product_name': 'Salmon Fillet', 'quantity': 2, 'unit_price': '30.00'},
            ],
        )
        # Second sync on same day
        result = LightspeedSalesSyncService.sync_sales(
            location=self.location_a,
            sales_date='2026-09-09',
            items=[
                {'product_name': 'Salmon Fillet', 'quantity': 3, 'unit_price': '30.00'},
            ],
        )
        self.assertEqual(result['total_revenue'], Decimal('150.00'))
        daily = DailySalesRecord.objects.get(location=self.location_a, date='2026-09-09')
        self.assertEqual(daily.sold_dishes.first().quantity_sold, 5)
