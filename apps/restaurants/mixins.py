"""
apps/restaurants/mixins.py
──────────────────────────
RestaurantAccessMixin — reusable queryset restriction for any viewset that
operates on restaurant-scoped data.

Usage:
    class IngredientViewSet(RestaurantAccessMixin, viewsets.ModelViewSet):
        restaurant_filter_field = 'restaurant_id'  # default; override if needed

        def get_queryset(self):
            qs = super().get_queryset()
            return self.filter_queryset_by_restaurant(qs)

The mixin inspects the authenticated user's role:
  - SUPER_ADMIN       → returns the full queryset unchanged
  - RESTAURANT_ADMIN  → filters to restaurants assigned to that user only

Enforcement happens at the database layer, not in the frontend, so a
Restaurant Admin cannot bypass it by changing a query parameter.
"""

from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied


class RestaurantAccessMixin:
    """
    Mixin for ModelViewSet subclasses that store a ForeignKey to Restaurant.

    Attributes:
        restaurant_filter_field (str): The ORM lookup path from the queryset
            model to the Restaurant PK. Defaults to 'restaurant_id'.
    """

    restaurant_filter_field: str = 'restaurant_id'

    def filter_queryset_by_restaurant(self, queryset):
        """
        Return queryset filtered to the restaurants the current user may access.
        """
        user = self.request.user

        if not user.is_authenticated:
            return queryset.none()

        if user.is_super_admin:
            return queryset

        # RESTAURANT_ADMIN: restrict to assigned restaurants
        assigned_ids = user.get_assigned_restaurant_ids()
        filter_field = getattr(self, 'restaurant_filter_field', None) or getattr(self, 'location_filter_field', 'restaurant_id')
        return queryset.filter(**{f'{filter_field}__in': assigned_ids})

    def filter_queryset_by_location(self, queryset):
        """Backward-compatible alias for filter_queryset_by_restaurant."""
        return self.filter_queryset_by_restaurant(queryset)

    def get_requested_restaurant_id(self):
        """
        Extract restaurant UUID from request query parameters.
        Supports 'restaurant_id', 'restaurant', 'location_id', and 'location'.
        """
        params = getattr(self.request, 'query_params', {})
        return (
            params.get('restaurant_id')
            or params.get('restaurant')
            or params.get('location_id')
            or params.get('location')
        )

    def assert_restaurant_access(self, restaurant_id) -> None:
        """
        Raise DRFPermissionDenied if the current user cannot access the
        given restaurant_id. Call this in create() / perform_create() before
        saving objects that reference an explicit restaurant.
        """
        user = self.request.user
        if user.is_super_admin:
            return
        assigned_ids = list(user.get_assigned_restaurant_ids())
        # Coerce to str for UUID comparison safety
        if str(restaurant_id) not in [str(i) for i in assigned_ids]:
            raise DRFPermissionDenied(
                'You do not have permission to access this restaurant.'
            )

    def assert_location_access(self, location_id) -> None:
        """Backward-compatible alias for assert_restaurant_access."""
        return self.assert_restaurant_access(location_id)


# Backward-compatible alias
LocationAccessMixin = RestaurantAccessMixin
