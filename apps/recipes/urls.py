from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet, RecipeItemViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'items', RecipeItemViewSet, basename='recipe-items')

urlpatterns = router.urls
