from rest_framework.routers import DefaultRouter

from .views import LocationViewSet

router = DefaultRouter()
router.register(r'', LocationViewSet, basename='locations')

urlpatterns = router.urls
