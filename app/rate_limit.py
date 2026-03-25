"""Simple in-memory rate limiter. Replace with Redis for multi-instance."""
import time
from collections import defaultdict

_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Returns True if request is allowed, False if rate-limited."""
    now = time.time()
    bucket = _buckets[key]
    # Remove expired entries
    _buckets[key] = [t for t in bucket if now - t < window_seconds]
    if len(_buckets[key]) >= max_requests:
        return False
    _buckets[key].append(now)
    return True
