import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def notify_daily_dashboard_summary():
    """Send a daily dashboard summary to admin and manager users."""
    from apps.notifications.services import NotificationTemplates

    staff_users = User.objects.filter(is_active=True, is_staff=True)
    for user in staff_users:
        NotificationTemplates.daily_summary(user)

    logger.info(f'Sent daily dashboard summary notifications to {staff_users.count()} users')


@shared_task
def notify_low_stock_alerts():
    """Send inventory alerts for ingredients that are below their stock threshold."""
    from apps.notifications.services import NotificationTemplates

    try:
        from django.db.models import F
        from apps.inventory.models import Ingredient
    except ImportError:
        logger.warning('Inventory app not available yet; skipping low stock alert task.')
        return

    low_stock_items = Ingredient.objects.filter(current_stock__lte=F('min_stock_alert'))
    for ingredient in low_stock_items:
        for user in User.objects.filter(is_active=True, is_staff=True):
            NotificationTemplates.low_stock_alert(user, ingredient)

    logger.info(f'Sent low stock notifications for {low_stock_items.count()} ingredients')


@shared_task
def notify_lightspeed_sync_completed(location_name='Restaurant', records_synced=0):
    """Send a success notification after a Lightspeed sales sync completes."""
    from apps.notifications.services import NotificationTemplates

    for user in User.objects.filter(is_active=True, is_staff=True):
        NotificationTemplates.lightspeed_sync_completed(user, location_name, records_synced)

    logger.info('Lightspeed sync success notification sent')


@shared_task
def notify_profitability_alert(location_name='Restaurant', food_cost_pct=None):
    """Send a dashboard notification if food cost ratio is too high."""
    from apps.notifications.services import NotificationTemplates

    for user in User.objects.filter(is_active=True, is_staff=True):
        NotificationTemplates.profitability_alert(user, location_name, food_cost_pct)

    logger.info('Profitability alert notification sent')