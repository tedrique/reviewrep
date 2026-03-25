"""Simple in-memory rate limiting.

Defaults:
- generate: 10/min per user
- publish: 20/min per user

For production, swap storage to Redis and keep the same interface.
"""
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.buckets: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        now = time.time()
        bucket = self.buckets[key]
        # drop old timestamps
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


generate_limiter = RateLimiter(limit=10, window=60)
publish_limiter = RateLimiter(limit=20, window=60)


def check_generate(user_id: int) -> bool:
    return generate_limiter.allow(user_id)


def check_publish(user_id: int) -> bool:
    return publish_limiter.allow(user_id)

