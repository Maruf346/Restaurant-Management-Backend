from rest_framework.routers import DefaultRouter

from .views import LightspeedConfigViewSet

router = DefaultRouter()
router.register(r'', LightspeedConfigViewSet, basename='lightspeed-config')

urlpatterns = router.urls
