from rest_framework.routers import DefaultRouter

from .views import DailySalesRecordViewSet, SoldDishRecordViewSet

router = DefaultRouter()
router.register(r'daily', DailySalesRecordViewSet, basename='daily-sales')
router.register(r'items', SoldDishRecordViewSet, basename='sold-dishes')

urlpatterns = router.urls
