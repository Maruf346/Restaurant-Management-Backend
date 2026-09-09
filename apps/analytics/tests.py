from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Ingredient
from apps.locations.models import Location
from apps.recipes.models import Category, Product, RecipeItem
from apps.sales.models import DailySalesRecord, SoldDishRecord


class DashboardAnalyticsTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(name='Downtown', code='DT3', currency='USD')
        self.category = Category.objects.create(location=self.location, name='Meals')
        self.ingredient = Ingredient.objects.create(
            location=self.location,
            name='Rice',
            base_unit='kg',
            current_stock=Decimal('20.000'),
            cost_per_base_unit=Decimal('1.50'),
            latest_purchase_price=Decimal('1.50'),
            min_stock_alert=Decimal('2.000'),
        )
        self.product = Product.objects.create(
            location=self.location,
            category=self.category,
            name='Chicken Rice Bowl',
            selling_price=Decimal('18.00'),
        )
        RecipeItem.objects.create(
            product=self.product,
            ingredient=self.ingredient,
            quantity=Decimal('0.300'),
            unit='kg',
        )

        self.daily_sales = DailySalesRecord.objects.create(
            location=self.location,
            date='2026-09-09',
            total_revenue=Decimal('18.00'),
            total_cost=Decimal('0.45'),
        )
        self.sold_item = SoldDishRecord.objects.create(
            daily_sales=self.daily_sales,
            product=self.product,
            quantity_sold=1,
            unit_selling_price=Decimal('18.00'),
            total_sales=Decimal('18.00'),
            theoretical_cost=Decimal('0.45'),
        )
        self.sold_item.calculate_metrics()

    def test_dashboard_summary_aggregates_profitability(self):
        from apps.analytics.services import DashboardAnalyticsService

        summary = DashboardAnalyticsService.get_dashboard_summary(self.location, '2026-09-09', '2026-09-09')

        self.assertEqual(summary['total_revenue'], Decimal('18.00'))
        self.assertEqual(summary['total_cost'], Decimal('0.45'))
        self.assertEqual(summary['gross_profit'], Decimal('17.55'))
        self.assertEqual(summary['food_cost_pct'], Decimal('2.50'))

    def test_dish_performance_lists_products_with_margin(self):
        from apps.analytics.services import DashboardAnalyticsService

        rows = DashboardAnalyticsService.get_dish_performance(self.location, '2026-09-09', '2026-09-09')

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['product_name'], 'Chicken Rice Bowl')
        self.assertEqual(rows[0]['gross_profit'], Decimal('17.55'))
        self.assertEqual(rows[0]['margin_pct'], Decimal('97.50'))
