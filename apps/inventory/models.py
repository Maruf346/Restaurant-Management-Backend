import uuid

from django.db import models

from apps.locations.models import Location
from apps.users.models import User


class UnitChoices(models.TextChoices):
    GRAM = 'g', 'Gram (g)'
    KILOGRAM = 'kg', 'Kilogram (kg)'
    MILLILITER = 'ml', 'Milliliter (ml)'
    LITER = 'l', 'Liter (L)'
    PIECE = 'pcs', 'Pieces (pcs)'
    PACK = 'pack', 'Pack'
    DOZEN = 'dozen', 'Dozen'


class Ingredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=200)
    base_unit = models.CharField(max_length=20, choices=UnitChoices.choices, default=UnitChoices.GRAM)
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    min_stock_alert = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    latest_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_per_base_unit = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    supplier_name = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.location.name})'


class PurchaseEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='purchase_entries')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='purchase_entries')
    supplier_name = models.CharField(max_length=200, blank=True, default='')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, choices=UnitChoices.choices, default=UnitChoices.GRAM)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    purchase_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchase_date', '-created_at']

    def __str__(self):
        return f'{self.ingredient.name} - {self.quantity} {self.unit}'
