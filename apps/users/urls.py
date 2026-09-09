from django.urls import path

from .views import *

app_name = 'users'

urlpatterns = [
    # User profile
    path('me/', MeView.as_view(), name='current-user'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    # Restaurant Admin management (Super Admin only)
    path('restaurant-admins/', CreateRestaurantAdminView.as_view(), name='restaurant-admins'),
    path('restaurant-admins/list/', ListRestaurantAdminsView.as_view(), name='list-restaurant-admins'),
]
