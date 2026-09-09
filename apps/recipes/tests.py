from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Ingredient
from apps.locations.models import Location
from apps.recipes.models import Category, Product, RecipeItem


class InventoryAndRecipeCalculationTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(
            name='Downtown',
            code='DT1',
            currency='USD',
        )
        self.ingredient = Ingredient.objects.create(
            location=self.location,
            name='Tomato',
            base_unit='kg',
            current_stock=Decimal('3.000'),
            cost_per_base_unit=Decimal('2.50'),
            latest_purchase_price=Decimal('2.50'),
            min_stock_alert=Decimal('1.000'),
        )
        self.category = Category.objects.create(location=self.location, name='Mains')
        self.product = Product.objects.create(
            location=self.location,
            category=self.category,
            name='Tomato Pasta',
            selling_price=Decimal('20.00'),
        )
        self.recipe_item = RecipeItem.objects.create(
            product=self.product,
            ingredient=self.ingredient,
            quantity=Decimal('0.500'),
            unit='kg',
        )

    def test_ingredient_purchase_updates_stock_and_cost(self):
        self.ingredient.apply_purchase(quantity=Decimal('2.000'), unit='kg', purchase_price=Decimal('8.00'))

        self.assertEqual(self.ingredient.current_stock, Decimal('5.000'))
        self.assertEqual(self.ingredient.cost_per_base_unit, Decimal('4.00'))
        self.assertEqual(self.ingredient.latest_purchase_price, Decimal('8.00'))

    def test_recipe_item_cost_is_based_on_base_unit_conversion(self):
        self.assertEqual(self.recipe_item.ingredient_cost(), Decimal('1.25'))

    def test_product_recipe_cost_and_food_cost_percentage(self):
        self.assertEqual(self.product.recipe_cost(), Decimal('1.25'))
        self.assertEqual(self.product.food_cost_percentage(), Decimal('6.25'))

    def test_product_margin_is_calculated_for_pricing(self):
        self.assertEqual(self.product.gross_profit(), Decimal('18.75'))
        self.assertEqual(self.product.margin_percentage(), Decimal('93.75'))
