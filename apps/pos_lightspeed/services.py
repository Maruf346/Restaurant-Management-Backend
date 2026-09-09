from decimal import Decimal

from apps.recipes.models import Product
from apps.sales.models import DailySalesRecord, SoldDishRecord


class LightspeedSalesSyncService:
    @staticmethod
    def sync_sales(location, sales_date, items):
        daily_record, _ = DailySalesRecord.objects.get_or_create(
            location=location,
            date=sales_date,
        )

        total_revenue = Decimal('0')
        total_cost = Decimal('0')

        for item in items:
            product_name = item.get('product_name')
            quantity = int(item.get('quantity', 0) or 0)
            unit_price = Decimal(str(item.get('unit_price', '0') or '0'))

            if not product_name or quantity <= 0:
                continue

            product = Product.objects.filter(location=location, name=product_name).first()
            if product is None:
                product = Product.objects.filter(location=location, lightspeed_item_id=str(item.get('product_id', ''))).first()
            if product is None:
                continue

            sold_dish, _ = daily_record.sold_dishes.get_or_create(
                product=product,
                defaults={'quantity_sold': 0, 'unit_selling_price': unit_price},
            )
            sold_dish.quantity_sold += quantity
            sold_dish.unit_selling_price = unit_price
            sold_dish.calculate_metrics()

            total_revenue += sold_dish.total_sales
            total_cost += sold_dish.theoretical_cost

        daily_record.calculate_totals()
        return {
            'location': location,
            'date': sales_date,
            'total_revenue': daily_record.total_revenue,
            'total_cost': daily_record.total_cost,
            'gross_profit': daily_record.gross_profit,
            'food_cost_pct': daily_record.food_cost_pct,
            'profit_margin_pct': daily_record.profit_margin_pct,
        }
