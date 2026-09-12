from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet, RecipeItemViewSet, RecentUpdateViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'items', RecipeItemViewSet, basename='recipe-items')
router.register(r'recent-updates', RecentUpdateViewSet, basename='recent-updates')

urlpatterns = router.urls
