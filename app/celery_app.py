import os
from celery import Celery
from app.logger import setup_logging

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

celery_app = Celery("reviewbot", broker=REDIS_URL, backend=RESULT_URL)

# Celery config: short visibility timeout, acks_late to avoid loss
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=30,
    task_soft_time_limit=25,
    beat_schedule={
        "sla-scan-15m": {
            "task": "app.sla.sla_scan_task",
            "schedule": 900.0,
        },
        "roi-weekly": {
            "task": "app.roi.weekly_digest",
            "schedule": 604800.0,  # weekly (BETA)
        },
    },
)


@celery_app.on_after_configure.connect
def _configure_logging(sender, **kwargs):
    setup_logging()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=3)
def send_notification_task(self, account_id: int, event: str, payload: dict):
    from app.notifications import send_notifications
    try:
        send_notifications(account_id, event, payload)
    except Exception as exc:
        raise self.retry(exc=exc)
