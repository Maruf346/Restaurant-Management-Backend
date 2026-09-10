from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # Auth (login / logout / refresh)
    path('auth/', include('apps.users.auth_urls')),

    # User profile + management (me, change-password, restaurant-admins)
    path('users/', include('apps.users.urls')),

    # Restaurant management
    path('restaurants/', include('apps.restaurants.urls')),

    # Inventory
    path('inventory/', include('apps.inventory.urls')),

    # Recipes / menu
    path('recipes/', include('apps.recipes.urls')),

    # Sales records
    path('sales/', include('apps.sales.urls')),

    # Lightspeed OAuth actions + config management
    path('pos-lightspeed/', include('apps.pos_lightspeed.urls')),

    # Analytics
    path('analytics/', include('apps.analytics.urls')),

    # Notifications
    path('notifications/', include('apps.notifications.urls')),

    # API schema and documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='redoc'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
