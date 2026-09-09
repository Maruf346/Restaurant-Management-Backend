"""
apps/pos_lightspeed/tasks.py
────────────────────────────
Celery background tasks for Lightspeed POS integration.

Includes:
  - Periodic token refresh for tokens approaching expiration
  - Asynchronous sales synchronization
  - Webhook processing
  - Daily sales reconciliation
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

from celery import shared_task
from django.utils import timezone

from .models import LightspeedConfig, LightspeedConnectionStatus
from .services import LightspeedSalesFetcher, LightspeedSalesSyncService
from .token_refresh import LightspeedTokenRefreshService, TokenRefreshLockError

logger = logging.getLogger(__name__)


@shared_task(name='pos_lightspeed.refresh_near_expiry_tokens')
def refresh_near_expiry_lightspeed_tokens():
    """
    Periodic task running every 5-10 minutes.
    Finds all active Lightspeed connections whose access tokens are near expiry
    (within 10 minutes) and proactively refreshes them.
    """
    active_configs = LightspeedConfig.objects.filter(
        status=LightspeedConnectionStatus.CONNECTED
    )
    refreshed_count = 0

    for config in active_configs:
        if config.is_token_near_expiry(buffer_seconds=600):
            try:
                LightspeedTokenRefreshService.refresh_if_needed(config)
                refreshed_count += 1
            except Exception as exc:
                logger.error("Failed periodic refresh for config %s: %s", config.id, exc)

    logger.info("Periodic token refresh complete: refreshed %s tokens.", refreshed_count)
    return {'refreshed_count': refreshed_count}


@shared_task(name='pos_lightspeed.sync_lightspeed_sales', bind=True, max_retries=3, default_retry_delay=60)
def sync_lightspeed_sales(self, config_id: str, date_str: Optional[str] = None):
    """
    Fetch sales from Lightspeed API for a location on a specific date,
    calculate costing metrics, and update DailySalesRecord.
    """
    try:
        config = LightspeedConfig.objects.select_related('location').get(id=config_id)
    except LightspeedConfig.DoesNotExist:
        logger.error("LightspeedConfig with id %s does not exist.", config_id)
        return {'error': 'Config not found'}

    if not config.is_connected:
        logger.warning("Config %s is not connected (status=%s); skipping sync.", config_id, config.status)
        return {'status': 'skipped', 'reason': 'not_connected'}

    sync_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else (timezone.now().date() - timedelta(days=1))

    try:
        fetcher = LightspeedSalesFetcher(config)
        items = fetcher.fetch_orders_for_date(sync_date)
        sync_result = LightspeedSalesSyncService.sync_sales(
            location=config.location,
            sales_date=sync_date,
            items=items,
        )

        config.last_synced_at = timezone.now()
        config.save(update_fields=['last_synced_at', 'updated_at'])

        logger.info(
            "Successfully synced sales for %s on %s (%d items). Revenue: %s",
            config.location.name,
            sync_date,
            len(items),
            sync_result.get('total_revenue'),
        )
        return {
            'location_id': str(config.location.id),
            'date': sync_date.isoformat(),
            'items_count': len(items),
            'total_revenue': str(sync_result.get('total_revenue')),
        }
    except Exception as exc:
        logger.error("Error syncing sales for config %s on %s: %s", config_id, sync_date, exc)
        config.record_error(f"Sync failed for {sync_date}: {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.critical("Max retries exceeded for syncing config %s on %s", config_id, sync_date)
            return {'error': str(exc), 'status': 'failed'}


@shared_task(name='pos_lightspeed.process_lightspeed_webhook', bind=True)
def process_lightspeed_webhook(self, event_payload: Dict[str, Any]):
    """
    Process an incoming Lightspeed webhook payload asynchronously.
    Identifies the matching location and updates sales accordingly.
    """
    logger.info("Processing webhook payload: %s", event_payload)
    account_id = str(event_payload.get('account_id') or event_payload.get('accountId', ''))
    business_location_id = str(
        event_payload.get('business_location_id')
        or event_payload.get('locationId', '')
    )

    query = LightspeedConfig.objects.filter(status=LightspeedConnectionStatus.CONNECTED)
    if business_location_id:
        config = query.filter(business_location_id=business_location_id).first()
    elif account_id:
        config = query.filter(account_id=account_id).first()
    else:
        config = None

    if not config:
        logger.warning(
            "No active LightspeedConfig matched webhook identifiers: account=%s, location=%s",
            account_id,
            business_location_id,
        )
        return {'status': 'unmatched'}

    today_str = timezone.now().date().isoformat()
    sync_lightspeed_sales.delay(str(config.id), today_str)
    return {'status': 'sync_queued', 'config_id': str(config.id)}


@shared_task(name='pos_lightspeed.reconcile_lightspeed_sales')
def reconcile_lightspeed_sales(config_id: Optional[str] = None, date_str: Optional[str] = None):
    """
    Reconciles sales for yesterday (or specified date).
    Can be run for a single location or across all connected locations.
    """
    target_date_str = date_str or (timezone.now().date() - timedelta(days=1)).isoformat()

    if config_id:
        configs = LightspeedConfig.objects.filter(pk=config_id, status=LightspeedConnectionStatus.CONNECTED)
    else:
        configs = LightspeedConfig.objects.filter(status=LightspeedConnectionStatus.CONNECTED, auto_sync_enabled=True)

    queued = 0
    for cfg in configs:
        sync_lightspeed_sales.delay(str(cfg.id), target_date_str)
        queued += 1

    logger.info("Reconciliation queued for %d locations for date %s", queued, target_date_str)
    return {'queued_count': queued, 'date': target_date_str}
