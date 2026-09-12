import uuid
from decimal import Decimal

from django.db import models

from apps.inventory.models import Ingredient, UnitChoices
from apps.restaurants.models import Restaurant


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=30, default='#10b981')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('restaurant', 'name')
        ordering = ['sort_order', 'name']

    def avg_margin_percentage(self):
        products = [p for p in self.products.all() if p.is_active]
        if not products:
            return Decimal('0')
        total_selling = sum((p.selling_price for p in products), Decimal('0'))
        if total_selling > 0:
            total_profit = sum((p.gross_profit() for p in products), Decimal('0'))
            return (total_profit / total_selling) * Decimal('100')
        margins = [p.margin_percentage() for p in products]
        return sum(margins, Decimal('0')) / Decimal(len(margins))

    def avg_food_cost_percentage(self):
        margin = self.avg_margin_percentage()
        return max(Decimal('100') - margin, Decimal('0')) if margin > 0 else Decimal('0')

    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=200)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    lightspeed_item_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    description = models.TextField(blank=True, default='')
    picture = models.ImageField(upload_to='product_pictures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('restaurant', 'name')
        ordering = ['name']

    @property
    def no_of_ingredients(self):
        return len(self.recipe_items.all())

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
        return f'{self.name} ({self.restaurant.name})'


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


class UpdateType(models.TextChoices):
    RECIPE_UPDATED = 'recipe_updated', 'Recipe Updated'
    COST_ALERT = 'cost_alert', 'Cost Alert'
    PRODUCT_ADDED = 'product_added', 'Product Added'


class RecentUpdate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='recent_updates')
    update_type = models.CharField(max_length=50, choices=UpdateType.choices, default=UpdateType.RECIPE_UPDATED)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    actor_name = models.CharField(max_length=150, blank=True, default='System')
    actor_role = models.CharField(max_length=80, blank=True, default='')
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='recent_updates')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.restaurant.name})'
