from rest_framework.routers import DefaultRouter

from .views import LocationViewSet

app_name = 'locations'

router = DefaultRouter()
router.register(r'', LocationViewSet, basename='location')

urlpatterns = router.urls
