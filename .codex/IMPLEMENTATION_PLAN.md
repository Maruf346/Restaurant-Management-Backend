# Restaurant Profitability System — Implementation Plan

## 1. Objective
Build a scalable restaurant cost and profitability backend that connects to Lightspeed POS, imports sales automatically, maps those sales to recipes and ingredients, calculates theoretical usage and profit margins, then exposes clean API endpoints for the existing frontend.

This should be implemented in phases, with a clear MVP first and optional expansion later.

---

## 2. Recommended Scope Strategy

### MVP (Phase 1–3)
Focus on the features that create the highest business value:
- One restaurant location
- Lightspeed sales import
- Menu items + recipes
- Ingredient purchase pricing
- Daily theoretical food cost
- Dish-level profitability
- Dashboard summary
- Basic variance reporting

### Post-MVP (Phase 4–6)
- Multi-location support
- Advanced inventory variance analytics
- User roles and access control refinement
- Deployment automation and AWS setup
- More advanced reporting and exports

---

## 3. Recommended Application Structure
Keep the current base layout, but organize the project by business domain instead of one generic app.

Suggested structure:

```text
apps/
  locations/
  inventory/
  recipes/
  sales/
  pos_lightspeed/
  analytics/
  users/
  api/
  notifications/
```

Notes:
- The project already has `apps/users`, `apps/api`, and `apps/notifications`, which is fine to keep.
- The domain apps above better reflect the business logic described in the requirements.
- We do not need to force a 1:1 match with the sample architecture in the project details file; the backend should remain modular and practical.

---

## 4. Domain Model Priorities

### 4.1 Authentication & Users
- Custom user model
- Roles: Admin, Restaurant Manager, Inventory, Chef, Reports Viewer
- JWT-based authentication
- Location access control

### 4.2 Locations
- Restaurant/location record
- Currency and timezone
- Lightspeed connection details

### 4.3 Inventory
- Ingredient
- PurchaseEntry
- StockTake
- Unit converter logic
- Purchase price tracking

### 4.4 Recipes
- Category
- Product / Menu Item
- RecipeItem
- Cost calculation by ingredient + recipe qty

### 4.5 Sales & POS Sync
- DailySalesRecord
- SoldDishRecord
- Lightspeed API integration
- Daily scheduled sync task
- mapping from POS item IDs to local products

### 4.6 Analytics
- Theoretical usage calculation
- Actual vs theoretical variance
- Daily / weekly / monthly profit summaries
- Best and worst dishes

---

## 5. Implementation Phases

### Phase 1 — Foundation
Deliverables:
- Django project + DRF setup
- PostgreSQL config
- `.env` management
- Custom user model
- JWT auth
- Basic RBAC permissions
- Core project settings and app wiring

Priority decisions:
- Use `apps.users` as the auth/user domain if consistent with current repo
- Keep `core/settings.py` as the source of installed apps and environment configuration

### Phase 2 — Master Data and Product Logic
Deliverables:
- Location model
- Ingredient model and purchase tracking
- Unit choices and conversion logic
- Category + Product + RecipeItem models
- Product cost calculation
- Purchase price update flow

Important rule:
- All recipe calculations must be based on a consistent unit conversion layer so ingredient costs remain accurate.

### Phase 3 — Sales Sync and Cost Engine
Deliverables:
- Lightspeed OAuth flow
- Scheduled sync task
- Sales import mapping logic
- Theoretical usage calculation by menu item
- Daily sales summary aggregation
- Dish profit calculation per sale / period

This is the core business engine of the project.

### Phase 4 — Variance and Reporting
Deliverables:
- Actual stock vs theoretical usage comparison
- Variance percentage and thresholds
- Dashboard KPIs
- Daily / weekly / monthly reporting
- Best and worst dishes

### Phase 5 — API and Frontend Integration
Deliverables:
- DRF serializers and viewsets
- Authentication endpoints
- Inventory and product CRUD APIs
- Dashboard analytics endpoints
- CORS and API contract validation with the existing frontend

### Phase 6 — Deployment
Deliverables:
- Docker setup
- PostgreSQL in AWS RDS
- Redis + Celery task queue
- Optional S3 for media assets
- CI/CD setup and deployment guidance

---

## 6. Data Flow Design

```text
Lightspeed POS
  -> Daily sync
  -> Sales/import pipeline
  -> Map POS item IDs to Product records
  -> Calculate theoretical ingredient usage from recipes
  -> Compare with actual purchase/stock data
  -> Generate dashboard and variance analytics
  -> Expose JSON API to frontend
```

This is the correct business flow for the system and should drive all backend modules.

---

## 7. MVP API Priorities
The first version should expose these endpoints only:

- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`
- `GET /api/v1/locations/`
- `GET /api/v1/ingredients/`
- `POST /api/v1/ingredients/`
- `GET /api/v1/products/`
- `POST /api/v1/products/`
- `GET /api/v1/analytics/dashboard/`
- `GET /api/v1/analytics/dish-performance/`
- `POST /api/v1/lightspeed/trigger-sync/`
etc. 

This is enough for the frontend to start working with real business data without overbuilding the API surface too early.

---

## 8. Key Engineering Decisions

### Keep it modular
Do not place all logic into one app. Domain-based apps will be easier to maintain and test.

### Keep one source of truth for costing
Ingredient costing, product costing, and variance calculations should all use the same formulas and service layer.

### Start with one location
Multiple-location support is important, but the first implementation should work reliably for one location before scaling.

### Treat Lightspeed sync as a background system
The POS import should not block the user workflow; it should run via Celery tasks and create auditable records.

---

## 9. Risks to Manage
- Recipe mapping from POS menu items may not be 1:1 with internal product IDs
- Ingredient units may differ across suppliers and recipes
- Certain menu items may have complex modifiers or bundled components
- Actual inventory data may be missing or inconsistent
- Lightspeed API credential and token handling must be robust

Mitigation:
- create a clear product mapping table
- standardize units early
- support modifier handling in the sync layer
- allow manual reconciliation if stock data is incomplete

---

## 10. Recommended Next Step
Continue with build execution in a phased sequence:
1. Set up the project foundation and auth
2. Create the core domain apps
3. Implement the ingredient + recipe models
4. Build the sales sync service
5. Implement the analytics engine
6. Add the API layer and verify with frontend consumption

This plan is realistic for the repo and matches the client requirements without trying to build the entire platform in one giant step.
