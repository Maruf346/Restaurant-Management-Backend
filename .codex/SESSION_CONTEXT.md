# Restaurant Backend Context Snapshot

## Project
Restaurant Management Backend for a multi-location restaurant profitability system.

## Current status (2026-09-09)
- Django project base is stable and passes startup validation.
- The custom user model, project settings, ASGI, and Celery wiring are in place.
- The restaurant domain apps are created and active:
  - apps.users
  - apps.locations
  - apps.inventory
  - apps.recipes
  - apps.sales
  - apps.pos_lightspeed
  - apps.api
  - apps.notifications
- Ingredient costing and recipe cost logic are implemented and validated.
- Daily sales profitability and POS import logic are implemented and validated.
- The next implementation phase is the analytics dashboard API and reporting endpoints.

## Key files
- core/settings.py
- core/urls.py
- apps/recipes/models.py
- apps/inventory/models.py
- apps/sales/models.py
- apps/pos_lightspeed/services.py
- apps/api/urls.py

## Business rules in effect
- Use location-scoped inventory and recipes.
- Product cost is calculated from ingredient usage and unit conversion.
- Daily sales records compute revenue, cost, gross profit, food cost %, and margin %.
- POS sync is modeled through a `LightspeedSalesSyncService` and should be consumed by Celery tasks later.
- Dashboard analytics should aggregate by date range and location.

## Validation evidence
- `manage.py check` passed successfully.
- Recipe cost tests passed.
- Sales profitability tests passed.

## Current next target
Build analytics dashboard APIs for summary and dish performance using existing `DailySalesRecord` and `SoldDishRecord` data.
