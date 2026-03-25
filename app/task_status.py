from app.celery_app import celery_app


def get_task_status(task_id: str) -> dict:
    res = celery_app.AsyncResult(task_id)
    return {
        "id": task_id,
        "state": res.state,
        "ready": res.ready(),
        "success": res.successful(),
        "result": str(res.result)[:200] if res.ready() else None,
    }
