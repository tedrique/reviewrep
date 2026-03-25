from app.celery_app import celery_app
from app.alerts import sla_scan_and_alert


@celery_app.task
def sla_scan_task():
    sla_scan_and_alert()
