import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Read directly from env — never from a pre-evaluated f-string
REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
REDIS_PORT = os.environ.get('REDIS_PORT') or '6379'
BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'

app = Celery('core')

# Explicitly set broker BEFORE config_from_object so it's never overridden
# by a stale value from settings that was evaluated at a different time
app.config_from_object('django.conf:settings', namespace='CELERY')

# Explicitly override broker/backend with live env values
# This is the definitive fix — these always win
app.conf.broker_url = BROKER_URL
app.conf.result_backend = BROKER_URL

app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


app.conf.beat_schedule = {
    'daily-dashboard-summary': {
        'task': 'apps.notifications.tasks.notify_daily_dashboard_summary',
        'schedule': crontab(hour=8, minute=0),
    },
    'low-stock-alerts': {
        'task': 'apps.notifications.tasks.notify_low_stock_alerts',
        'schedule': crontab(hour=9, minute=0),
    },
    'refresh-lightspeed-tokens': {
        'task': 'pos_lightspeed.refresh_near_expiry_tokens',
        'schedule': crontab(minute='*/5'),
    },
    'daily-lightspeed-reconciliation': {
        'task': 'pos_lightspeed.reconcile_lightspeed_sales',
        'schedule': crontab(hour=2, minute=0),
    },
}