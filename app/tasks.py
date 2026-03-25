"""Compatibility wrapper for the local task queue."""
from app.task_queue import enqueue


def run_async(fn, *args, **kwargs):
    enqueue(fn, *args, **kwargs)
