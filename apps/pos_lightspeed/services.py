"""
apps/pos_lightspeed/services.py
───────────────────────────────
Business services for Lightspeed POS integration.

Components:
  - LightspeedSalesFetcher: HTTP/API concern — fetches and normalizes raw Lightspeed data
  - LightspeedSalesSyncService: Business/Costing concern — calculates sales metrics and updates DB
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from apps.recipes.models import Product
from apps.sales.models import DailySalesRecord, SoldDishRecord

from .client import LightspeedApiClient, LightspeedApiError
from .models import LightspeedConfig

logger = logging.getLogger(__name__)


class LightspeedSalesFetcher:
    """
    Fetches raw order lines from the Lightspeed K-Series API and normalizes
    them into standard dictionaries expected by LightspeedSalesSyncService.
    """

    def __init__(self, config: LightspeedConfig):
        self.config = config
        self.client = LightspeedApiClient(config)

    def fetch_orders_for_date(self, sales_date) -> List[Dict[str, Any]]:
        """
        Fetch all order items for a given date (date or str YYYY-MM-DD).
        Normalizes order lines into:
            [
                {
                    'product_id': '...',
                    'product_name': '...',
                    'quantity': 2,
                    'unit_price': '15.50',
                },
                ...
            ]
        """
        date_str = sales_date.isoformat() if hasattr(sales_date, 'isoformat') else str(sales_date)

        try:
            raw_orders = self.client.get_orders(date_from=date_str, date_to=date_str)
        except LightspeedApiError as exc:
            logger.error("Failed to fetch Lightspeed orders for %s: %s", date_str, exc)
            raise

        normalized_items: List[Dict[str, Any]] = []

        for order in raw_orders:
            # Handle K-Series order structure (lines, order_lines, or items)
            order_lines = (
                order.get('orderLines')
                or order.get('order_lines')
                or order.get('lines')
                or order.get('items')
                or []
            )
            for line in order_lines:
                product_id = str(
                    line.get('productId')
                    or line.get('product_id')
                    or line.get('itemId')
                    or line.get('id', '')
                )
                product_name = (
                    line.get('productName')
                    or line.get('product_name')
                    or line.get('name')
                    or ''
                )
                qty = line.get('quantity') or line.get('count', 1)
                unit_price = (
                    line.get('price')
                    or line.get('unitPrice')
                    or line.get('unit_price')
                    or '0'
                )

                if product_name and float(qty) > 0:
                    normalized_items.append({
                        'product_id': product_id,
                        'product_name': product_name,
                        'quantity': int(qty),
                        'unit_price': str(unit_price),
                    })

        return normalized_items


class LightspeedSalesSyncService:
    """
    Business service that takes normalized sold item data and updates/creates
    DailySalesRecord and SoldDishRecord with costing metrics.
    """

    @staticmethod
    def sync_sales(location, sales_date, items: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                product = Product.objects.filter(
                    location=location,
                    lightspeed_item_id=str(item.get('product_id', '')),
                ).first()
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
