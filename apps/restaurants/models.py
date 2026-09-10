import uuid

from django.conf import settings
from django.db import models


class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    currency = models.CharField(max_length=10, default='USD')
    timezone = models.CharField(max_length=64, default='UTC')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserRestaurant(models.Model):
    """
    Through-model that assigns restaurant users to specific restaurants.

    Designed for ManyToMany so the system can support multiple admins per
    restaurant in the future. Currently, RESTAURANT_ADMIN users are restricted
    to their assigned restaurant(s).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_restaurants',
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='user_restaurants',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restaurant_assignments_made',
    )

    class Meta:
        unique_together = ('user', 'restaurant')
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.user.email} → {self.restaurant.name}'
