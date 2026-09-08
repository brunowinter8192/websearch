# INFRASTRUCTURE
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

MAX_REQUESTS = 10
WINDOW_SECONDS = 60.0

_limiters: dict[str, "RateLimiter"] = {}


class RateLimiter:
    def __init__(self, max_requests: int = MAX_REQUESTS, window_seconds: float = WINDOW_SECONDS):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._tokens: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        logger.debug("Rate limit: acquiring token")
        async with self._lock:
            now = time.monotonic()
            self._tokens = [t for t in self._tokens if now - t < self._window_seconds]

            if len(self._tokens) >= self._max_requests:
                oldest = self._tokens[0]
                wait = self._window_seconds - (now - oldest)
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._tokens = [t for t in self._tokens if now - t < self._window_seconds]

            self._tokens.append(time.monotonic())


def get_limiter(engine_name: str, max_requests: int = MAX_REQUESTS, window_seconds: float = WINDOW_SECONDS) -> RateLimiter:
    if engine_name not in _limiters:
        _limiters[engine_name] = RateLimiter(max_requests, window_seconds)
    return _limiters[engine_name]
