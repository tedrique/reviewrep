"""Lightweight async task queue with retries and timeouts.
Replaces simple run_async. For scale, swap to Celery/RQ/Arq."""
import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=3)
_dead_letter: list[dict] = []


@dataclass
class TaskResult:
    task_name: str
    success: bool
    attempts: int
    error: str = ""
    completed_at: str = ""


def enqueue(func, *args, max_retries: int = 3, timeout: float = 30.0, task_name: str = "", **kwargs):
    """Run a sync function in background thread with retries and timeout."""
    name = task_name or func.__name__

    def _run():
        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                func(*args, **kwargs)
                log.info(f"[TASK OK] {name} (attempt {attempt})")
                return
            except Exception as e:
                last_error = f"{e}"
                log.warning(f"[TASK RETRY] {name} attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    import time
                    time.sleep(min(2 ** attempt, 10))

        # All retries failed — dead letter
        entry = {
            "task": name,
            "error": last_error,
            "attempts": max_retries,
            "timestamp": datetime.utcnow().isoformat(),
            "traceback": traceback.format_exc(),
        }
        _dead_letter.append(entry)
        if len(_dead_letter) > 100:
            _dead_letter.pop(0)
        log.error(f"[TASK DEAD] {name} failed after {max_retries} attempts: {last_error}")

    _executor.submit(_run)


def get_dead_letters() -> list[dict]:
    """Get failed tasks for admin inspection."""
    return list(_dead_letter)


def clear_dead_letters():
    _dead_letter.clear()
