from django.urls import path

from .views import (
    ChangePasswordView,
    MeView,
    RestaurantAdminDetailView,
    RestaurantAdminListCreateView,
    ToggleRestaurantAdminStatusView,
)

app_name = 'users'

urlpatterns = [
    # ── Current user profile ─────────────────────────────────────────────
    # GET  — retrieve profile (with profile_picture URL)
    # PATCH — update full_name and/or profile_picture (multipart/form-data)
    path('me/', MeView.as_view(), name='current-user'),

    # ── Password management ──────────────────────────────────────────────
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    # ── Restaurant Admin management ──────────────────────────────────────
    # GET  — list admins (scoped: super admin sees all, restaurant admin sees co-admins)
    # POST — create/invite a new admin (with invitation email)
    path('restaurant-admins/', RestaurantAdminListCreateView.as_view(), name='restaurant-admins'),

    # GET  — retrieve a single admin by UUID
    path('restaurant-admins/<int:pk>/', RestaurantAdminDetailView.as_view(), name='restaurant-admin-detail'),

    # PATCH — toggle is_active (super admin only)
    path('restaurant-admins/<int:pk>/toggle-status/', ToggleRestaurantAdminStatusView.as_view(), name='toggle-restaurant-admin-status'),
]
