"""Backwards compat — redirects to task_queue."""
from app.task_queue import enqueue

def run_async(fn, *args, **kwargs):
    """Deprecated. Use task_queue.enqueue directly."""
    enqueue(fn, *args, **kwargs)
