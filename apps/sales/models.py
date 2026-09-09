import uuid

from django.db import models

from apps.locations.models import Location
from apps.recipes.models import Product


class DailySalesRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='daily_sales')
    date = models.DateField()
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    food_cost_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    profit_margin_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.location.name} - {self.date}'


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

    def __str__(self):
        return f'{self.product.name} - {self.quantity_sold} sold'
