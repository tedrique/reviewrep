"""Rate limiting — prefers Redis, falls back to in-memory buckets."""
import time
from collections import defaultdict, deque
from app.config import REDIS_URL

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis optional in dev
    redis = None

_redis_client = None
if redis and REDIS_URL:
    try:
        _redis_client = redis.Redis.from_url(REDIS_URL)
        _redis_client.ping()
    except Exception:
        _redis_client = None


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


def _allow_redis(key: str, limit: int, window: int) -> bool | None:
    if not _redis_client:
        return None
    try:
        with _redis_client.pipeline() as pipe:
            pipe.incr(key, 1)
            pipe.expire(key, window, nx=True)
            count, _ = pipe.execute()
            return int(count) <= limit
    except Exception:
        return None


def _allow(key: str, limit: int, window: int) -> bool:
    res = _allow_redis(key, limit, window)
    if res is None:
        return _limiter.allow(key, limit, window)
    return res


def check_generate(user_id: int) -> bool:
    return _allow(f"gen:{user_id}", 10, 60)


def check_publish(user_id: int) -> bool:
    return _allow(f"pub:{user_id}", 20, 60)


def check_ip(ip: str) -> bool:
    return _allow(f"ip:{ip}", 240, 60)


def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    return _allow(key, max_requests, window_seconds)
