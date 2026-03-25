# Celery task status (bulk actions)

## Enabling result backend
- Set `CELERY_RESULT_BACKEND` to your Redis URL (e.g., `redis://.../1`).
- In `app/celery_app.py`, Celery uses the same backend as broker by default (already works if Redis).

## UI polling approach (planned)
- Expose a lightweight endpoint `/tasks/{task_id}` returning state from `AsyncResult`.
- Frontend: after submitting bulk generate/approve/publish, store returned task_id and poll every 2–3s until `SUCCESS` or `FAILURE`.
- Show toast/banner with final state.

## Current state
- Bulk generate/approve/publish are enqueued but UI only shows “queued” banner.
- Implementing status requires returning task_id from POST handlers and a small JS poller.
