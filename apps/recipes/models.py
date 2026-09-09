import uuid
from decimal import Decimal

from django.db import models

from apps.inventory.models import Ingredient, UnitChoices
from apps.locations.models import Location


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=30, default='#10b981')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('location', 'name')
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=200)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    lightspeed_item_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'name')
        ordering = ['name']

    def recipe_cost(self):
        return sum((item.ingredient_cost() for item in self.recipe_items.all()), Decimal('0'))

    def gross_profit(self):
        return self.selling_price - self.recipe_cost()

    def food_cost_percentage(self):
        if self.selling_price <= 0:
            return Decimal('0')
        return (self.recipe_cost() / self.selling_price) * Decimal('100')

    def margin_percentage(self):
        if self.selling_price <= 0:
            return Decimal('0')
        return (self.gross_profit() / self.selling_price) * Decimal('100')

    def __str__(self):
        return f'{self.name} ({self.location.name})'


class RecipeItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recipe_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='recipe_usages')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit = models.CharField(max_length=20, choices=UnitChoices.choices, default=UnitChoices.GRAM)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ingredient__name']

    def ingredient_cost(self):
        return self.ingredient.cost_for_quantity(self.quantity, self.unit)

    def __str__(self):
        return f'{self.product.name} - {self.ingredient.name}'
