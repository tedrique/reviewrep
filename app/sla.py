"""Celery beat task to scan SLA breaches and alert."""
from app.celery_app import celery_app
from app.alerts import sla_scan_and_alert


@celery_app.task(name="app.sla.sla_scan_task")
def sla_scan_task():
    sla_scan_and_alert()
