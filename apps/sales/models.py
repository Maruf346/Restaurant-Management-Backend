import uuid
from decimal import Decimal

from django.db import models

from apps.restaurants.models import Restaurant
from apps.recipes.models import Product


class DailySalesRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='daily_sales')
    date = models.DateField()
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    food_cost_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    profit_margin_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('restaurant', 'date')
        ordering = ['-date']

    def calculate_totals(self):
        sold_dishes = self.sold_dishes.all()
        self.total_revenue = sum((item.total_sales for item in sold_dishes), Decimal('0'))
        self.total_cost = sum((item.theoretical_cost for item in sold_dishes), Decimal('0'))
        self.gross_profit = self.total_revenue - self.total_cost

        if self.total_revenue > 0:
            self.food_cost_pct = (self.total_cost / self.total_revenue) * Decimal('100')
            self.profit_margin_pct = (self.gross_profit / self.total_revenue) * Decimal('100')
        else:
            self.food_cost_pct = Decimal('0')
            self.profit_margin_pct = Decimal('0')

        self.save(update_fields=['total_revenue', 'total_cost', 'gross_profit', 'food_cost_pct', 'profit_margin_pct', 'updated_at'])
        return self

    def __str__(self):
        return f'{self.restaurant.name} - {self.date}'


class SoldDishRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    daily_sales = models.ForeignKey(DailySalesRecord, on_delete=models.CASCADE, related_name='sold_dishes')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sold_dish_records')
    quantity_sold = models.PositiveIntegerField(default=0)
    unit_selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    theoretical_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    margin_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-total_sales']

    def calculate_metrics(self):
        recipe_cost = self.product.recipe_cost() if self.product else Decimal('0')
        self.theoretical_cost = recipe_cost * Decimal(self.quantity_sold)
        self.total_sales = self.unit_selling_price * Decimal(self.quantity_sold)
        self.gross_profit = self.total_sales - self.theoretical_cost

        if self.total_sales > 0:
            self.margin_pct = (self.gross_profit / self.total_sales) * Decimal('100')
        else:
            self.margin_pct = Decimal('0')

        self.save(update_fields=['quantity_sold', 'unit_selling_price', 'total_sales', 'theoretical_cost', 'gross_profit', 'margin_pct'])
        self.daily_sales.calculate_totals()
        return self

    def __str__(self):
        return f'{self.product.name} - {self.quantity_sold} sold'
