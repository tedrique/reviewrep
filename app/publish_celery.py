"""Celery task wrapper for publishing responses to Google."""
from app.celery_app import celery_app
from app.publish_task import _do_publish


@celery_app.task(bind=True, max_retries=1, default_retry_delay=2, name="app.publish_celery.publish_response_task")
def publish_response_task(self, account_id: int, actor_user_id: int, response_id: int, refresh_token: str, access_token: str):
    """Dispatch publish to worker and retry once on transient errors."""
    try:
        _do_publish(account_id, actor_user_id, response_id, refresh_token, access_token)
    except Exception as exc:
        raise self.retry(exc=exc)
