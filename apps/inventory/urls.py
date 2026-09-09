from rest_framework.routers import DefaultRouter

from .views import IngredientViewSet, PurchaseEntryViewSet

router = DefaultRouter()
router.register(r'ingredients', IngredientViewSet, basename='ingredients')
router.register(r'purchases', PurchaseEntryViewSet, basename='purchases')

urlpatterns = router.urls
