from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Ingredient, PurchaseEntry, UnitChoices

# Threshold (%) above which a price increase triggers a cost-alert event.
COST_ALERT_THRESHOLD_PCT = Decimal('5')


def _maybe_log_cost_alert(ingredient, old_cost_per_base_unit, new_cost_per_base_unit):
    """
    If cost_per_base_unit rose by >= COST_ALERT_THRESHOLD_PCT, create a
    COST_ALERT RecentUpdate record for the restaurant.  Import is deferred
    inside the function to avoid a circular import.
    """
    if old_cost_per_base_unit is None or old_cost_per_base_unit <= 0:
        return
    if new_cost_per_base_unit <= old_cost_per_base_unit:
        return

    increase_pct = (
        (new_cost_per_base_unit - old_cost_per_base_unit)
        / old_cost_per_base_unit
        * Decimal('100')
    )
    if increase_pct < COST_ALERT_THRESHOLD_PCT:
        return

    # Deferred import to avoid circular dependency (inventory ↔ recipes)
    from apps.recipes.models import RecipeItem, UpdateType
    from apps.recipes.models import RecentUpdate

    affected_count = (
        RecipeItem.objects
        .filter(ingredient=ingredient)
        .values('product')
        .distinct()
        .count()
    )

    RecentUpdate.objects.create(
        restaurant=ingredient.restaurant,
        update_type=UpdateType.COST_ALERT,
        title=f'Cost Alert: {ingredient.name}',
        description=(
            f'Price increased by {increase_pct:.0f}%. '
            f'Affects {affected_count} recipe{"s" if affected_count != 1 else "."}'
        ),
        actor_name='System',
        actor_role='Inventory',
        metadata={
            'ingredient_id': str(ingredient.id),
            'old_cost_per_base_unit': str(old_cost_per_base_unit),
            'new_cost_per_base_unit': str(new_cost_per_base_unit),
            'increase_pct': str(round(increase_pct, 2)),
            'recipes_affected': affected_count,
        },
    )

UNIT_FAMILIES = {
    # Mass
    UnitChoices.GRAM: ('mass', Decimal('1')),
    UnitChoices.KILOGRAM: ('mass', Decimal('1000')),
    # Volume
    UnitChoices.MILLILITER: ('volume', Decimal('1')),
    UnitChoices.LITER: ('volume', Decimal('1000')),
    # Count / Discrete
    UnitChoices.PIECE: ('count', Decimal('1')),
    UnitChoices.PACK: ('count', Decimal('1')),
    UnitChoices.DOZEN: ('count', Decimal('12')),
}


def convert_units(quantity, from_unit, to_unit):
    """
    Convert a quantity from one unit to another within the same measurement family.
    Raises ValidationError if units belong to incompatible families or are unrecognized.
    """
    quantity = Decimal(str(quantity))
    if from_unit == to_unit:
        return quantity

    from_info = UNIT_FAMILIES.get(from_unit)
    to_info = UNIT_FAMILIES.get(to_unit)

    if not from_info:
        raise ValidationError(f"Unsupported unit: '{from_unit}'.")
    if not to_info:
        raise ValidationError(f"Unsupported unit: '{to_unit}'.")

    from_family, from_factor = from_info
    to_family, to_factor = to_info

    if from_family != to_family:
        raise ValidationError(
            f"Cannot convert between '{from_unit}' ({from_family}) and '{to_unit}' ({to_family})."
        )

    # Convert to family canonical base, then to target unit
    canonical_qty = quantity * from_factor
    return canonical_qty / to_factor


def adjust_stock_for_recipe_item(ingredient_id, delta_base_qty):
    """
    Atomically adjust an ingredient's current_stock by *delta_base_qty*
    (already converted to the ingredient's base unit).

    Convention:
      +delta → stock is consumed (ingredient added/increased in a recipe)
      -delta → stock is restored  (ingredient removed/decreased from a recipe)

    Must be called inside a transaction.atomic() block.
    Uses select_for_update() to prevent concurrent stock corruption.
    """
    delta_base_qty = Decimal(str(delta_base_qty))
    if delta_base_qty == Decimal('0'):
        return

    ingredient = Ingredient.objects.select_for_update().get(id=ingredient_id)
    ingredient.current_stock -= delta_base_qty          # subtract: usage reduces stock
    ingredient.save(update_fields=['current_stock', 'updated_at'])


def record_purchase_entry(*, restaurant, ingredient_id, quantity, unit, purchase_price, purchase_date, supplier_name='', created_by=None):
    """
    Record a new purchase entry, update the ingredient stock atomically,
    recalculate unit cost and cost per base unit, and snapshot supplier name.
    """
    quantity = Decimal(str(quantity))
    purchase_price = Decimal(str(purchase_price))

    if quantity <= Decimal('0'):
        raise ValidationError({'quantity': 'Purchase quantity must be greater than zero.'})
    if purchase_price < Decimal('0'):
        raise ValidationError({'purchase_price': 'Purchase price cannot be negative.'})

    with transaction.atomic():
        ingredient = Ingredient.objects.select_for_update().get(id=ingredient_id)

        if ingredient.restaurant_id != restaurant.id:
            raise ValidationError({'ingredient': 'Ingredient does not belong to the selected restaurant.'})

        # Snapshot old cost before mutation (for cost-alert comparison)
        old_cost_per_base_unit = ingredient.cost_per_base_unit

        # Calculate base unit quantity
        base_quantity = convert_units(quantity, from_unit=unit, to_unit=ingredient.base_unit)
        if base_quantity <= Decimal('0'):
            raise ValidationError({'quantity': 'Converted quantity must be greater than zero.'})

        # Calculate unit economics
        unit_cost = purchase_price / quantity
        cost_per_base_unit = purchase_price / base_quantity if base_quantity > 0 else Decimal('0')

        # Use ingredient supplier as fallback if supplier_name was not provided
        effective_supplier = supplier_name.strip() if supplier_name else ingredient.supplier_name

        # Update ingredient state
        ingredient.current_stock += base_quantity
        ingredient.latest_purchase_price = purchase_price
        if cost_per_base_unit > 0:
            ingredient.cost_per_base_unit = cost_per_base_unit
        if effective_supplier:
            ingredient.supplier_name = effective_supplier
        ingredient.save(update_fields=['current_stock', 'latest_purchase_price', 'cost_per_base_unit', 'supplier_name', 'updated_at'])

        # Create purchase record snapshot
        purchase = PurchaseEntry.objects.create(
            restaurant=restaurant,
            ingredient=ingredient,
            supplier_name=effective_supplier,
            quantity=quantity,
            unit=unit,
            purchase_price=purchase_price,
            unit_cost=unit_cost,
            purchase_date=purchase_date,
            created_by=created_by,
        )

        # Fire cost-alert if price rose significantly
        _maybe_log_cost_alert(ingredient, old_cost_per_base_unit, ingredient.cost_per_base_unit)

        return purchase


def update_purchase_entry(purchase, *, quantity=None, unit=None, purchase_price=None, purchase_date=None, supplier_name=None):
    """
    Update an existing purchase entry and adjust ingredient stock and economics accordingly.
    """
    with transaction.atomic():
        ingredient = Ingredient.objects.select_for_update().get(id=purchase.ingredient_id)

        old_base_quantity = convert_units(purchase.quantity, from_unit=purchase.unit, to_unit=ingredient.base_unit)

        new_quantity = Decimal(str(quantity)) if quantity is not None else purchase.quantity
        new_unit = unit if unit is not None else purchase.unit
        new_price = Decimal(str(purchase_price)) if purchase_price is not None else purchase.purchase_price
        new_supplier = supplier_name if supplier_name is not None else purchase.supplier_name
        new_date = purchase_date if purchase_date is not None else purchase.purchase_date

        if new_quantity <= Decimal('0'):
            raise ValidationError({'quantity': 'Purchase quantity must be greater than zero.'})
        if new_price < Decimal('0'):
            raise ValidationError({'purchase_price': 'Purchase price cannot be negative.'})

        new_base_quantity = convert_units(new_quantity, from_unit=new_unit, to_unit=ingredient.base_unit)
        delta_base_quantity = new_base_quantity - old_base_quantity

        # Adjust ingredient stock
        ingredient.current_stock += delta_base_quantity
        unit_cost = new_price / new_quantity
        cost_per_base_unit = new_price / new_base_quantity if new_base_quantity > 0 else Decimal('0')

        # If this was or is the latest purchase, refresh latest price and cost
        latest_purchase = (
            PurchaseEntry.objects.filter(ingredient=ingredient)
            .order_by('-purchase_date', '-created_at')
            .first()
        )
        if latest_purchase is None or latest_purchase.id == purchase.id:
            ingredient.latest_purchase_price = new_price
            if cost_per_base_unit > 0:
                ingredient.cost_per_base_unit = cost_per_base_unit
            if new_supplier:
                ingredient.supplier_name = new_supplier

        ingredient.save(update_fields=['current_stock', 'latest_purchase_price', 'cost_per_base_unit', 'supplier_name', 'updated_at'])

        # Update purchase entry record
        purchase.quantity = new_quantity
        purchase.unit = new_unit
        purchase.purchase_price = new_price
        purchase.unit_cost = unit_cost
        purchase.supplier_name = new_supplier
        purchase.purchase_date = new_date
        purchase.save(update_fields=['quantity', 'unit', 'purchase_price', 'unit_cost', 'supplier_name', 'purchase_date'])

        return purchase


def delete_purchase_entry(purchase):
    """
    Delete a purchase entry and reverse its stock addition on the ingredient.
    """
    with transaction.atomic():
        ingredient = Ingredient.objects.select_for_update().get(id=purchase.ingredient_id)
        base_quantity = convert_units(purchase.quantity, from_unit=purchase.unit, to_unit=ingredient.base_unit)

        # Roll back stock
        ingredient.current_stock -= base_quantity

        # Delete purchase entry
        purchase_id = purchase.id
        purchase.delete()

        # Re-evaluate latest purchase economics from remaining records
        remaining_latest = (
            PurchaseEntry.objects.filter(ingredient=ingredient)
            .order_by('-purchase_date', '-created_at')
            .first()
        )
        if remaining_latest:
            rem_base_qty = convert_units(remaining_latest.quantity, from_unit=remaining_latest.unit, to_unit=ingredient.base_unit)
            ingredient.latest_purchase_price = remaining_latest.purchase_price
            if rem_base_qty > 0:
                ingredient.cost_per_base_unit = remaining_latest.purchase_price / rem_base_qty
            if remaining_latest.supplier_name:
                ingredient.supplier_name = remaining_latest.supplier_name

        ingredient.save(update_fields=['current_stock', 'latest_purchase_price', 'cost_per_base_unit', 'supplier_name', 'updated_at'])
