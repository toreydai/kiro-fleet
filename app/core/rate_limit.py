"""进程内登录限流。单机 Compose 部署无需引入 Redis。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()
            if len(timestamps) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="登录尝试过于频繁，请稍后再试",
                    headers={"Retry-After": str(window_seconds)},
                )
            timestamps.append(now)


login_limiter = SlidingWindowRateLimiter()


def limit_login(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    login_limiter.check(client, get_settings().LOGIN_RATE_LIMIT_PER_MINUTE)
