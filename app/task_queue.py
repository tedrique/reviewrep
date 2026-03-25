"""Lightweight task queue with retries and dead-letter logging.

This is in-process and thread-based for simplicity. Swap the backend for
Celery/RQ/Arq by keeping the `enqueue` signature.
"""
from typing import Callable
import threading
import traceback
import json
import time

from app.database import log_dead_letter


def _run_with_retries(fn: Callable, args, kwargs, attempts: int, task_name: str):
    for i in range(attempts):
        try:
            fn(*args, **kwargs)
            return
        except Exception as e:
            if i == attempts - 1:
                payload = json.dumps({"args": args, "kwargs": kwargs}, default=str)[:2000]
                log_dead_letter(task_name, payload, f"{e}\n{traceback.format_exc()}")
            else:
                time.sleep(1.5)


def enqueue(fn: Callable, *args, attempts: int = 3, task_name: str = ""):
    name = task_name or fn.__name__
    t = threading.Thread(target=_run_with_retries, args=(fn, args, {}, attempts, name), daemon=True)
    t.start()
    return t
