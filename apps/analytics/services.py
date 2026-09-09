from decimal import Decimal

from django.db.models import Sum

from apps.sales.models import DailySalesRecord, SoldDishRecord


class DashboardAnalyticsService:
    @staticmethod
    def get_dashboard_summary(location, start_date, end_date):
        records = DailySalesRecord.objects.filter(location=location, date__range=[start_date, end_date])

        total_revenue = records.aggregate(total=Sum('total_revenue'))['total'] or Decimal('0')
        total_cost = records.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
        gross_profit = total_revenue - total_cost

        if total_revenue > 0:
            food_cost_pct = (total_cost / total_revenue) * Decimal('100')
            profit_margin_pct = (gross_profit / total_revenue) * Decimal('100')
        else:
            food_cost_pct = Decimal('0')
            profit_margin_pct = Decimal('0')

        return {
            'location': location,
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'gross_profit': gross_profit,
            'food_cost_pct': food_cost_pct,
            'profit_margin_pct': profit_margin_pct,
            'days': records.count(),
        }

    @staticmethod
    def get_dish_performance(location, start_date, end_date):
        items = SoldDishRecord.objects.filter(
            daily_sales__location=location,
            daily_sales__date__range=[start_date, end_date],
        ).select_related('product', 'daily_sales')

        rows = []
        for item in items:
            rows.append({
                'product_name': item.product.name,
                'quantity_sold': item.quantity_sold,
                'total_sales': item.total_sales,
                'theoretical_cost': item.theoretical_cost,
                'gross_profit': item.gross_profit,
                'margin_pct': item.margin_pct,
            })

        return rows
