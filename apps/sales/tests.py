from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Ingredient
from apps.locations.models import Location
from apps.recipes.models import Category, Product, RecipeItem
from apps.sales.models import DailySalesRecord, SoldDishRecord


class SalesAnalyticsTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(name='Downtown', code='DT2', currency='USD')
        self.category = Category.objects.create(location=self.location, name='Entrees')
        self.ingredient = Ingredient.objects.create(
            location=self.location,
            name='Chicken',
            base_unit='kg',
            current_stock=Decimal('10.000'),
            cost_per_base_unit=Decimal('8.00'),
            latest_purchase_price=Decimal('8.00'),
            min_stock_alert=Decimal('2.000'),
        )
        self.product = Product.objects.create(
            location=self.location,
            category=self.category,
            name='Grilled Chicken Bowl',
            selling_price=Decimal('24.00'),
        )
        RecipeItem.objects.create(
            product=self.product,
            ingredient=self.ingredient,
            quantity=Decimal('0.300'),
            unit='kg',
        )

    def test_sales_snapshot_calculates_profitability(self):
        daily_record = DailySalesRecord.objects.create(
            location=self.location,
            date='2026-09-09',
            total_revenue=Decimal('24.00'),
            total_cost=Decimal('2.40'),
        )

        sold_dish = SoldDishRecord.objects.create(
            daily_sales=daily_record,
            product=self.product,
            quantity_sold=1,
            unit_selling_price=Decimal('24.00'),
            total_sales=Decimal('24.00'),
            theoretical_cost=Decimal('2.40'),
        )

        sold_dish.calculate_metrics()
        self.assertEqual(sold_dish.gross_profit, Decimal('21.60'))
        self.assertEqual(sold_dish.margin_pct, Decimal('90.00'))

        daily_record.calculate_totals()
        self.assertEqual(daily_record.total_cost, Decimal('2.40'))
        self.assertEqual(daily_record.gross_profit, Decimal('21.60'))
        self.assertEqual(daily_record.food_cost_pct, Decimal('10.00'))
        self.assertEqual(daily_record.profit_margin_pct, Decimal('90.00'))

    def test_lightspeed_sync_service_builds_daily_record(self):
        from apps.pos_lightspeed.services import LightspeedSalesSyncService

        sync_result = LightspeedSalesSyncService.sync_sales(
            location=self.location,
            sales_date='2026-09-09',
            items=[{
                'product_name': 'Grilled Chicken Bowl',
                'quantity': 2,
                'unit_price': '24.00',
            }],
        )

        self.assertEqual(sync_result['total_revenue'], Decimal('48.00'))
        self.assertEqual(sync_result['total_cost'], Decimal('4.80'))
        self.assertEqual(sync_result['gross_profit'], Decimal('43.20'))
        self.assertEqual(sync_result['food_cost_pct'], Decimal('10.00'))
