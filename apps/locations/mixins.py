"""
apps/locations/mixins.py
────────────────────────
LocationAccessMixin — reusable queryset restriction for any viewset that
operates on location-scoped data.

Usage:
    class IngredientViewSet(LocationAccessMixin, viewsets.ModelViewSet):
        location_filter_field = 'location_id'  # default; override if needed

        def get_queryset(self):
            qs = super().get_queryset()
            return self.filter_queryset_by_location(qs)

The mixin inspects the authenticated user's role:
  - SUPER_ADMIN  → returns the full queryset unchanged
  - RESTAURANT_ADMIN → filters to locations assigned to that user only

Enforcement happens at the database layer, not in the frontend, so a
Restaurant Admin cannot bypass it by changing a query parameter.
"""

from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied


class LocationAccessMixin:
    """
    Mixin for ModelViewSet subclasses that store a ForeignKey to Location.

    Attributes:
        location_filter_field (str): The ORM lookup path from the queryset
            model to the Location PK. Defaults to 'location_id'.
    """

    location_filter_field: str = 'location_id'

    def filter_queryset_by_location(self, queryset):
        """
        Return queryset filtered to the locations the current user may access.

        Must be called explicitly in get_queryset():

            def get_queryset(self):
                qs = super().get_queryset()
                return self.filter_queryset_by_location(qs)
        """
        user = self.request.user

        if not user.is_authenticated:
            return queryset.none()

        if user.is_super_admin:
            return queryset

        # RESTAURANT_ADMIN: restrict to assigned locations
        assigned_ids = user.get_assigned_location_ids()
        return queryset.filter(**{f'{self.location_filter_field}__in': assigned_ids})

    def assert_location_access(self, location_id) -> None:
        """
        Raise DRFPermissionDenied if the current user cannot access the
        given location_id.  Call this in create() / perform_create() before
        saving objects that reference an explicit location.
        """
        user = self.request.user
        if user.is_super_admin:
            return
        assigned_ids = list(user.get_assigned_location_ids())
        # Coerce to str for UUID comparison safety
        if str(location_id) not in [str(i) for i in assigned_ids]:
            raise DRFPermissionDenied(
                'You do not have permission to access this location.'
            )
