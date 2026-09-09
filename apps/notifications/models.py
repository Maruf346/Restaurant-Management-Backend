from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class NotificationType(models.TextChoices):
    # Auth
    WELCOME = 'welcome', 'Welcome'
    PASSWORD_UPDATED = 'pass_updated', 'Password Updated'
    PASSWORD_CHANGED = 'pass_changed', 'Password Changed'

    # Restaurant operations
    DAILY_SUMMARY = 'daily_summary', 'Daily Summary'
    LIGHTSPEED_SYNC_COMPLETED = 'lightspeed_sync_completed', 'Lightspeed Sync Completed'
    SALES_IMPORT_COMPLETED = 'sales_import_completed', 'Sales Import Completed'
    LOW_STOCK_ALERT = 'low_stock_alert', 'Low Stock Alert'
    PROFITABILITY_ALERT = 'profitability_alert', 'Profitability Alert'
    RECIPE_UPDATED = 'recipe_updated', 'Recipe Updated'
    PURCHASE_LOGGED = 'purchase_logged', 'Purchase Logged'
    MENU_ITEM_UPDATED = 'menu_item_updated', 'Menu Item Updated'
    SYSTEM_ALERT = 'system_alert', 'System Alert'

    # Admin / general
    NEW_USER = 'new_user', 'New User Joined'


class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f'{self.title} — {self.user.email}'
