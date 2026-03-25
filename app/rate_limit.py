"""Rate limiting — in-memory with optional Redis upgrade."""
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self):
        self._buckets: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_limiter = RateLimiter()


def check_generate(user_id: int) -> bool:
    return _limiter.allow(f"gen:{user_id}", 10, 60)


def check_publish(user_id: int) -> bool:
    return _limiter.allow(f"pub:{user_id}", 20, 60)


def check_ip(ip: str) -> bool:
    return _limiter.allow(f"ip:{ip}", 240, 60)


def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    return _limiter.allow(key, max_requests, window_seconds)
