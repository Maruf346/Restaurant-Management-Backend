import logging

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from .models import Notification, NotificationPriority, NotificationType

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Web-only notification service for dashboard and admin events."""

    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
    ):
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )

        ws_success = NotificationService._send_websocket(
            user_id=str(user.id),
            notification_id=str(notification.id),
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
            created_at=notification.created_at.isoformat(),
        )

        if ws_success:
            logger.info(f'Notification sent via WebSocket to {user.email}: {notification_type}')
        else:
            logger.warning(f'WebSocket delivery failed for {user.email}: {notification_type}')

        return notification

    @staticmethod
    def _send_websocket(user_id, notification_id, notification_type, title, body, data, priority, created_at):
        try:
            channel_layer = get_channel_layer()
            group_name = f'user_{user_id}'

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification_id': notification_id,
                    'notification_type': notification_type,
                    'title': title,
                    'body': body,
                    'data': data,
                    'priority': priority,
                    'created_at': created_at,
                },
            )
            return True
        except Exception as exc:
            logger.error(f'WebSocket send failed for user {user_id}: {str(exc)}')
            return False

    @staticmethod
    def send_to_admins(notification_type, title, body, data=None):
        staff = User.objects.filter(is_staff=True, is_active=True)
        for user in staff:
            NotificationService.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )

    @staticmethod
    def send_to_managers(notification_type, title, body, data=None):
        managers = User.objects.filter(is_staff=True, is_superuser=False, is_active=True)
        for user in managers:
            NotificationService.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )


class NotificationTemplates:
    """Restaurant-specific notification templates used by the dashboard and Celery tasks."""

    @staticmethod
    def welcome(user):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.WELCOME,
            title='Welcome to ProfitPlate',
            body=f'Hi {getattr(user, "full_name", None) or user.email}, your account is ready.',
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def daily_summary(user, revenue=None, food_cost_pct=None, gross_profit=None, period='today'):
        revenue_text = f"{revenue:,.2f}" if revenue is not None else 'N/A'
        cost_text = f"{food_cost_pct:.1f}%" if food_cost_pct is not None else 'N/A'
        gross_profit_text = f"{gross_profit:,.2f}" if gross_profit is not None else 'N/A'

        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.DAILY_SUMMARY,
            title=f'{period.title()} Dashboard Summary',
            body=f'Revenue: {revenue_text} | Food cost: {cost_text} | Gross profit: {gross_profit_text}',
            data={'period': period, 'revenue': revenue_text, 'food_cost_pct': cost_text, 'gross_profit': gross_profit_text},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def lightspeed_sync_completed(user, location_name='Restaurant', records_synced=0):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.LIGHTSPEED_SYNC_COMPLETED,
            title='Lightspeed sync completed',
            body=f'{location_name} sales were synced successfully. {records_synced} records processed.',
            data={'location_name': location_name, 'records_synced': records_synced},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def sales_import_completed(user, location_name='Restaurant', total_revenue=0):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.SALES_IMPORT_COMPLETED,
            title='Sales import complete',
            body=f'{location_name} sales import finished. Total revenue: {total_revenue:,.2f}.',
            data={'location_name': location_name, 'total_revenue': float(total_revenue)},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def low_stock_alert(user, ingredient):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.LOW_STOCK_ALERT,
            title='Low stock alert',
            body=f'{ingredient.name} is below the minimum stock threshold. Current stock: {ingredient.current_stock}.',
            data={'ingredient_id': str(getattr(ingredient, 'id', '')), 'ingredient_name': ingredient.name, 'current_stock': str(ingredient.current_stock)},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def profitability_alert(user, location_name='Restaurant', food_cost_pct=None):
        if food_cost_pct is None:
            food_cost_pct = 0
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PROFITABILITY_ALERT,
            title='Food cost alert',
            body=f'{location_name} food cost is at {food_cost_pct:.1f}%. Review menu pricing and supplier costs.',
            data={'location_name': location_name, 'food_cost_pct': float(food_cost_pct)},
            priority=NotificationPriority.URGENT if float(food_cost_pct) > 35 else NotificationPriority.HIGH,
        )

    @staticmethod
    def recipe_updated(user, product_name, location_name='Restaurant'):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.RECIPE_UPDATED,
            title='Recipe updated',
            body=f'The recipe for {product_name} was updated for {location_name}.',
            data={'product_name': product_name, 'location_name': location_name},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def purchase_logged(user, ingredient_name, quantity, location_name='Restaurant'):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PURCHASE_LOGGED,
            title='Purchase recorded',
            body=f'{quantity} of {ingredient_name} was logged for {location_name}.',
            data={'ingredient_name': ingredient_name, 'quantity': str(quantity), 'location_name': location_name},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def menu_item_updated(user, product_name, location_name='Restaurant'):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.MENU_ITEM_UPDATED,
            title='Menu item updated',
            body=f'{product_name} was updated in {location_name}.',
            data={'product_name': product_name, 'location_name': location_name},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def system_alert(user, title, body, data=None):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            body=body,
            data=data or {},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def new_user_joined(new_user):
        NotificationService.send_to_admins(
            notification_type=NotificationType.NEW_USER,
            title='New user registered',
            body=f'{getattr(new_user, "full_name", None) or new_user.email} joined the platform.',
            data={'user_id': str(new_user.id)},
        )

