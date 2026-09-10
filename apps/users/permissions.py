"""
apps/users/permissions.py
─────────────────────────
Custom DRF permission classes for the ProfitPlate role system.

There are exactly two application-level roles:
  - SUPER_ADMIN       — full access to all locations and management operations
  - RESTAURANT_ADMIN  — restricted to their assigned location(s)

Super Admins are created via Django's createsuperuser command (is_superuser=True)
and then granted role=SUPER_ADMIN programmatically (see management commands or
admin). Restaurant Admins are created exclusively through the
POST /users/restaurant-admins/ endpoint.
"""

from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Allow access only to SUPER_ADMIN users."""

    message = 'You must be a Super Admin to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_super_admin
        )


class IsRestaurantAdmin(BasePermission):
    """Allow access only to RESTAURANT_ADMIN users."""

    message = 'You must be a Restaurant Admin to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_restaurant_admin
        )


class IsSuperAdminOrReadOnly(BasePermission):
    """
    Allow Super Admins full CRUD.
    Allow authenticated Restaurant Admins read-only access.
    """

    message = 'Write access requires Super Admin privileges.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        # Safe methods available to all authenticated users
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_super_admin


class IsSuperAdminOrIsOwner(BasePermission):
    """
    Super Admins may access any object.
    Restaurant Admins may only access objects belonging to their restaurant.
    Object-level enforcement is handled separately in get_queryset() via
    RestaurantAccessMixin.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
