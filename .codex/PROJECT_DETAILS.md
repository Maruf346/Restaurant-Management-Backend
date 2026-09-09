# Comprehensive Backend Architecture & Developer Implementation Guide
**Restaurant Management & Profitability System (PWA)**  
**Stack**: Django + Django REST Framework (DRF) | PostgreSQL | Celery + Redis | AWS (RDS, ECS/EC2, S3) | Lightspeed POS Integration

---

## 1. Executive Summary & System Overview

This backend powers the **ProfitPlate / Restaurant Management PWA**, designed to eliminate manual data entry by synchronizing daily sales from **Lightspeed POS**, combining them with dish recipes, ingredient purchase prices, and physical inventory stock counts to automatically calculate:
1. **Theoretical Ingredient Consumption & Food Cost** from POS sales.
2. **Actual Ingredient Usage & Variance** (Waste / Over-portioning / Spoilage).
3. **Daily / Weekly / Monthly Profitability Dashboards** (Revenue, Food Cost %, Gross Margin).
4. **Best & Least Profitable Dish Rankings**.
5. **Multi-Location & Role-Based Access Control** (Admin, Restaurant Manager, Inventory, Chef, Reports Viewer).

```
   ┌─────────────────────────────────────────────────────────┐
   │                   Lightspeed POS API                    │
   │           (Orders, Order Items, Modifiers)              │
   └───────────────────────────┬─────────────────────────────┘
                               │ Daily Scheduled / Webhook Sync
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │                Django REST Framework API                │
   │                                                         │
   │  ┌────────────────┐  ┌────────────────┐  ┌───────────┐  │
   │  │ Authentication │  │ Location Scoped│  │ Inventory │  │
   │  │   (JWT / RBAC) │  │  Multi-Tenant  │  │ & Recipes │  │
   │  └────────────────┘  └────────────────┘  └───────────┘  │
   │  ┌────────────────┐  ┌────────────────┐  ┌───────────┐  │
   │  │ Cost & Variance│  │ Lightspeed POS │  │ Dashboard │  │
   │  │  Calc Engine   │  │ Sync Workers   │  │& Analytics│  │
   │  └────────────────┘  └────────────────┘  └───────────┘  │
   └─────────────┬───────────────────────────┬───────────────┘
                 │                           │
                 ▼                           ▼
   ┌───────────────────────────┐   ┌─────────────────────────┐
   │    PostgreSQL Database    │   │  Celery Task Queue      │
   │   (AWS RDS - Relational)  │   │  + Redis (ElastiCache)  │
   └───────────────────────────┘   └─────────────────────────┘
```

---

## 2. Recommended Django Project Structure

 Already have proper structure. Analyze the code structure

---

## 3. Database Schema Design (PostgreSQL / Django Models)

### 3.1. `authentication` & `locations`
```python
# apps/locations/models.py
class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)  # e.g., "Casa Thai — Casa 1"
    brand = models.CharField(max_length=100) # e.g., "Casa Thai"
    currency = models.CharField(max_length=10, default="THB") # or EUR / USD
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

# apps/authentication/models.py
class RoleChoices(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    RESTAURANT_MANAGER = 'RESTAURANT_MANAGER', 'Restaurant Manager'
    INVENTORY = 'INVENTORY', 'Inventory'
    CHEF = 'CHEF', 'Chef'
    REPORTS_VIEWER = 'REPORTS_VIEWER', 'Reports Viewer'

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=30, choices=RoleChoices.choices, default=RoleChoices.RESTAURANT_MANAGER)
    assigned_locations = models.ManyToManyField(Location, blank=True, related_name="users")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    avatar_color = models.CharField(max_length=20, default="#c4b5a3")
```

### 3.2. `inventory` (Raw Ingredients & Purchases)
```python
# apps/inventory/models.py
class UnitChoices(models.TextChoices):
    GRAM = 'g', 'Gram (g)'
    KILOGRAM = 'kg', 'Kilogram (kg)'
    MILLILITER = 'ml', 'Milliliter (ml)'
    LITER = 'liters', 'Liter (L)'
    PIECE = 'pieces', 'Pieces (pcs)'
    PACK = 'pack', 'Pack'
    DOZEN = 'dozen', 'Dozen'

class Ingredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField(max_length=150)
    base_unit = models.CharField(max_length=20, choices=UnitChoices.choices)
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    min_stock_alert = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    latest_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0) # Price per base_unit
    cost_per_base_unit = models.DecimalField(max_digits=12, decimal_places=4, default=0.0) # Weighted average cost
    icon = models.CharField(max_length=50, blank=True, default="📦")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'name')

class PurchaseEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="purchases")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="purchase_records")
    supplier_name = models.CharField(max_length=150, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, choices=UnitChoices.choices)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2) # Total price paid
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4)       # Calculated price per unit
    purchase_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class StockTake(models.Model):
    """Physical inventory counts done periodically"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="stock_takes")
    count_date = models.DateField()
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_closed = models.BooleanField(default=False)

class StockTakeItem(models.Model):
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name="items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    physical_stock = models.DecimalField(max_digits=12, decimal_places=3) # Actual counted amount
```

### 3.3. `recipes` (Menu Items & Portioning)
```python
# apps/recipes/models.py
class Category(models.Model):
    id = models.CharField(max_length=50, primary_key=True) # e.g. "noodles", "burger"
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default="#10b981")
    sort_order = models.PositiveIntegerField(default=0)

class Product(models.Model):
    id = models.CharField(max_length=50, primary_key=True) # e.g. "p1", "p2" or UUID
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    name = models.CharField(max_length=200)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    image_color = models.CharField(max_length=20, default="#f97316")
    is_active = models.BooleanField(default=True)
    lightspeed_item_id = models.CharField(max_length=100, blank=True, null=True, db_index=True) # POS Mapping ID

    @property
    def total_food_cost(self):
        return sum(item.cost for item in self.recipe_items.all())

    @property
    def gross_profit(self):
        return self.selling_price - self.total_food_cost

    @property
    def margin_percentage(self):
        if self.selling_price > 0:
            return round(((self.selling_price - self.total_food_cost) / self.selling_price) * 100, 1)
        return 0.0

class RecipeItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recipe_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="recipe_usages")
    quantity = models.DecimalField(max_digits=10, decimal_places=3) # e.g. 150 (g), 0.2 (kg)
    unit = models.CharField(max_length=20, choices=UnitChoices.choices)

    @property
    def cost(self):
        """Calculates cost based on ingredient current cost converted to recipe unit"""
        # Unit conversion factor between self.unit and self.ingredient.base_unit
        factor = UnitConverter.convert(self.unit, self.ingredient.base_unit)
        converted_quantity = self.quantity * factor
        return round(converted_quantity * self.ingredient.cost_per_base_unit, 2)
```

### 3.4. `pos_lightspeed` & `sales`
```python
# apps/pos_lightspeed/models.py
class LightspeedConfig(models.Model):
    location = models.OneToOneField(Location, on_delete=models.CASCADE, related_name="lightspeed_config")
    api_url = models.URLField(default="https://api.lightspeed.app")
    client_id = models.CharField(max_length=200)
    client_secret = models.CharField(max_length=200)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    lightspeed_account_id = models.CharField(max_length=100)
    auto_sync_enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

# apps/sales/models.py
class DailySalesRecord(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="daily_sales")
    date = models.DateField(db_index=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    theoretical_food_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    actual_food_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gross_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    profit_margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    food_cost_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        unique_together = ('location', 'date')

class SoldDishRecord(models.Model):
    daily_sales = models.ForeignKey(DailySalesRecord, on_delete=models.CASCADE, related_name="sold_dishes")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_sold = models.PositiveIntegerField(default=0)
    unit_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2)
    theoretical_cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_theoretical_cost = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)
    margin_pct = models.DecimalField(max_digits=5, decimal_places=2)
```

---

## 4. Core Costing, Profitability & Variance Calculation Engine

The backend developer should implement a dedicated utility module (`apps/analytics/services/cost_engine.py`) using these exact business formulas:

### 4.1. Unit Conversion Matrix
Standardize all raw ingredients into SI units:
- Weight: `1 kg = 1000 g`
- Volume: `1 L = 1000 ml`
- Discrete: `1 dozen = 12 pcs / units`

### 4.2. Theoretical Ingredient Usage
For every closed order imported from Lightspeed on date $D$:
$$\text{Theoretical Usage}(I) = \sum_{P \in \text{Products}} \Big( \text{Quantity Sold}(P) \times \text{Recipe Quantity}(P, I) \Big)$$
$$\text{Theoretical Cost}(I) = \text{Theoretical Usage}(I) \times \text{Cost per Unit}(I)$$

### 4.3. Actual Consumption & Variance
When a physical stock count (StockTake) is submitted for date $D_2$ following $D_1$:
$$\text{Actual Usage} = \text{Opening Stock}(D_1) + \sum \text{Purchases}(D_1 \to D_2) - \text{Ending Stock}(D_2)$$
$$\text{Variance Quantity} = \text{Actual Usage} - \text{Theoretical Usage}$$
$$\text{Variance \%} = \left(\frac{\text{Actual Usage} - \text{Theoretical Usage}}{\text{Theoretical Usage}}\right) \times 100$$
- **Positive Variance ($>0$)**: Over-consumption (waste, over-portioning, theft, spoilage).
- **Negative Variance ($<0$)**: Under-portioning or inaccurate stock counting.

### 4.4. Dashboard KPI Aggregations
For the selected time window (Daily / Weekly / Monthly):
- $\text{Total Revenue} = \sum \text{Sales Amount}$
- $\text{Theoretical Food Cost} = \sum \text{Theoretical Cost of Sold Dishes}$
- $\text{Gross Profit} = \text{Total Revenue} - \text{Food Cost}$
- $\text{Food Cost \%} = \frac{\text{Theoretical Food Cost}}{\text{Total Revenue}} \times 100$
- $\text{Profit Margin \%} = \frac{\text{Gross Profit}}{\text{Total Revenue}} \times 100$
- $\Delta \text{ Change \%} = \frac{\text{Current Period} - \text{Previous Period}}{\text{Previous Period}} \times 100$

---

## 5. Lightspeed POS Integration Workflow

Lightspeed POS (Restaurant K-Series / O-Series) uses OAuth 2.0 and provides REST endpoints for receipts, financial reports, and catalog products.

### 5.1. Authentication & Token Lifecycle
1. Connect via OAuth 2.0 authorization URL:
   - `GET /api/v1/lightspeed/authorize/?location_id=<UUID>`
   - Lightspeed redirects back with `code` to `/api/v1/lightspeed/callback/`
   - Django exchanges `code` for `access_token` and `refresh_token`.
2. Automatic token refresh before scheduled tasks execute:
   - Check `token_expires_at`. If within 15 minutes of expiry, call `https://api.lightspeed.app/oauth/token` with `grant_type=refresh_token`.

### 5.2. Daily Automated Sync Pipeline (Celery Beat)
Schedule a Celery task nightly (e.g. at 02:00 AM local restaurant time) for each active location:

```python
# apps/pos_lightspeed/tasks.py
@shared_task
def sync_daily_sales_all_locations():
    for config in LightspeedConfig.objects.filter(auto_sync_enabled=True):
        sync_location_sales_for_date.delay(config.location_id, date.today() - timedelta(days=1))

@shared_task
def sync_location_sales_for_date(location_id, target_date):
    # 1. Fetch closed receipts/orders from Lightspeed API for target_date
    # 2. Iterate order items: match lightspeed_item_id -> Product
    # 3. Sum up quantities sold and revenue per Product
    # 4. Compute theoretical ingredient consumption for all recipe items
    # 5. Create or update DailySalesRecord & SoldDishRecord
    # 6. Recalculate Dashboard statistics & alert if variance threshold breached
```

---

## 6. REST API Endpoints Specification (Contract for Frontend)

The backend endpoints must directly serve the React frontend views:

### 6.1. Authentication & Users
| Method | Endpoint | Description | Frontend Consumer |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login/` | Return access token, refresh token, user data & assigned locations | `LoginPage.tsx`, `authStore.ts` |
| `POST` | `/api/v1/auth/refresh/` | Refresh JWT token | Background interceptor |
| `GET` | `/api/v1/auth/me/` | Current user profile, avatar, role | `AppLayout.tsx`, `SettingsPage.tsx` |
| `PATCH` | `/api/v1/auth/me/` | Update profile name, avatar | `SettingsPage.tsx` |
| `POST` | `/api/v1/auth/change-password/` | Update user password | `SettingsPage.tsx` |
| `GET` | `/api/v1/users/` | List all users (Role scoped) | `UsersPage.tsx` |
| `POST` | `/api/v1/users/` | Invite/create user with Role | `UsersPage.tsx` |
| `PATCH` | `/api/v1/users/<id>/` | Update role or toggle active state | `UsersPage.tsx` |

### 6.2. Locations & Settings
| Method | Endpoint | Description | Frontend Consumer |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/locations/` | List available locations for user | `AppLayout.tsx` (Location switch) |
| `GET` | `/api/v1/lightspeed/status/` | Check Lightspeed sync status & last sync timestamp | `SettingsPage.tsx` |
| `POST` | `/api/v1/lightspeed/trigger-sync/` | Manual on-demand sales sync | `SettingsPage.tsx` |

### 6.3. Inventory & Purchases
| Method | Endpoint | Description | Frontend Consumer |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/ingredients/?location_id=<id>` | List ingredients with stock & purchase price | `IngredientsPage.tsx` |
| `POST` | `/api/v1/ingredients/` | Create new raw ingredient | `IngredientsPage.tsx` |
| `PUT/PATCH` | `/api/v1/ingredients/<id>/` | Update ingredient, stock alert, purchase price | `IngredientsPage.tsx` |
| `DELETE` | `/api/v1/ingredients/<id>/` | Remove ingredient (checks recipe references) | `IngredientsPage.tsx` |
| `GET` | `/api/v1/purchases/?location_id=<id>` | List purchase history & price changes | `PurchasesPage.tsx` |
| `POST` | `/api/v1/purchases/` | Record new purchase entry (updates ingredient cost) | `PurchasesPage.tsx` |

### 6.4. Menu, Recipes & Products
| Method | Endpoint | Description | Frontend Consumer |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/categories/` | List dish categories | `InventoryPage.tsx` |
| `POST` | `/api/v1/categories/` | Create category | `InventoryPage.tsx` |
| `GET` | `/api/v1/products/?location_id=<id>` | List all menu dishes with calculated food costs | `InventoryPage.tsx`, `inventoryStore.ts` |
| `GET` | `/api/v1/products/<id>/` | Dish detail, recipe ingredients list & gross profit | `ProductDetailPage.tsx` |
| `POST` | `/api/v1/products/` | Create new dish with recipe ingredients | `AddEditProductPage.tsx` |
| `PUT/PATCH` | `/api/v1/products/<id>/` | Update dish selling price or recipe breakdown | `AddEditProductPage.tsx` |
| `DELETE` | `/api/v1/products/<id>/` | Delete dish | `ProductDetailPage.tsx` |

### 6.5. Dashboard, Profitability & Reports
| Method | Endpoint | Description | Frontend Consumer |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/dashboard/?location_id=<id>&range=daily\|weekly\|monthly` | Summary cards: revenue, food cost, gross profit, margin | `DashboardPage.tsx` |
| `GET` | `/api/v1/analytics/dish-performance/?location_id=<id>&range=...&type=best\|worst` | Top 4 best & least profitable dishes | `DashboardPage.tsx` |
| `GET` | `/api/v1/analytics/profitability/menu/?location_id=<id>&period=...` | Full table of dish food cost %, margin, sales count | `ProfitabilityPage.tsx` |
| `GET` | `/api/v1/analytics/profitability/variance/?location_id=<id>&period=...` | Theoretical vs actual ingredient usage & variance | `ProfitabilityPage.tsx` |
| `GET` | `/api/v1/analytics/reports/?location_id=<id>&period=...&date=...` | Executive summary report, top dishes, critical stocks | `ReportsPage.tsx` |

---

## 7. Security, Permissions & Multi-Tenancy

Implement clean, location-scoped Role-Based Access Control (RBAC):

```python
# apps/authentication/permissions.py
from rest_framework.permissions import BasePermission

class HasLocationAccess(BasePermission):
    """Ensure the user is authorized to access the requested location_id"""
    def has_permission(self, request, view):
        location_id = request.query_params.get('location_id') or request.data.get('location_id')
        if not location_id or request.user.role == 'ADMIN':
            return True
        return request.user.assigned_locations.filter(id=location_id).exists()

class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['ADMIN', 'RESTAURANT_MANAGER']

class IsInventoryOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['ADMIN', 'RESTAURANT_MANAGER', 'INVENTORY']
```

---

## 8. AWS Production Deployment Architecture

```
                       [ Route 53 + CloudFront ]
                                   │
                                   ▼
                    [ Application Load Balancer (ALB) ]
                                   │
          ┌────────────────────────┴────────────────────────┐
          ▼                                                 ▼
[ AWS ECS Fargate: Web API ]                      [ AWS ECS Fargate: Celery Worker ]
  (Gunicorn + Uvicorn DRF)                          (Daily Lightspeed Sync & Beat)
          │                                                 │
          ├────────────────────────┬────────────────────────┤
          ▼                        ▼                        ▼
[ AWS RDS PostgreSQL ]    [ AWS ElastiCache Redis ]   [ AWS S3 Bucket ]
  (Multi-AZ Database)       (Celery Broker & Cache)     (Avatars & Media)
```

### Production Checklist for AWS:
1. **Compute**: AWS ECS (Fargate) with auto-scaling or an EC2 instance running Docker Compose (`web`, `celery_worker`, `celery_beat`).
2. **Database**: Amazon RDS PostgreSQL 16 (Multi-AZ for high availability).
3. **Queue / Cache**: Amazon ElastiCache for Redis (used by Celery and DRF throttling/caching).
4. **Storage**: Amazon S3 for media uploads (ingredient receipts, user profile avatars) using `django-storages`.
5. **Environment Variables**: Managed securely via AWS Secrets Manager or Parameter Store (`DATABASE_URL`, `LIGHTSPEED_CLIENT_SECRET`, `SECRET_KEY`).
6. **Logging & Monitoring**: AWS CloudWatch logs and Sentry for error tracing.

---

## 9. Backend Developer Implementation Roadmap

| Phase | Duration | Scope & Deliverables |
| :--- | :--- | :--- |
| **Phase 1: Foundation & Auth** | Days 1–3 | Django setup, PostgreSQL configuration, Custom User model, JWT authentication, Location models, Role permissions. |
| **Phase 2: Master Data Management** | Days 4–7 | Raw Ingredients, Units, Purchase entries, Categories, Products/Dishes, and Recipe Items with dynamic food cost calculation logic. |
| **Phase 3: Costing & Analytics Engine** | Days 8–11 | Calculation services for Theoretical Usage, Actual Usage, Food Cost %, Gross Margin, and period aggregations (Daily, Weekly, Monthly). |
| **Phase 4: Lightspeed POS Integration** | Days 12–15 | Lightspeed OAuth2 client, sync services, mapping POS Item IDs to System Products, Celery beat scheduled night sync. |
| **Phase 5: Frontend Integration & Testing** | Days 16–18 | CORS configuration, API testing with Postman/Swagger (drf-spectacular), hooking frontend Axios/fetch calls to Django DRF endpoints. |
| **Phase 6: AWS Cloud Deployment** | Days 19–21 | Dockerfile, AWS RDS, ECS/EC2 setup, S3 media storage, CI/CD pipeline with GitHub Actions. |

