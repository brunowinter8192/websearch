# INFRASTRUCTURE
import asyncio
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

_rl_mod = importlib.import_module("src.search.rate_limiter")
RateLimiter = _rl_mod.RateLimiter

_acq_events: list[tuple[str, str, float, float | None]] = []

_pre_snapshots: list[dict] = []


# FUNCTIONS

def install_instrument() -> None:
    _require_limiter_internals()
    RateLimiter.acquire = _replacement_acquire


def _require_limiter_internals() -> None:
    if not hasattr(_rl_mod, "_limiters"):
        raise RuntimeError("src.search.rate_limiter no longer has _limiters: the branch instrument cannot name limiters")
    if not hasattr(RateLimiter, "acquire"):
        raise RuntimeError("RateLimiter no longer has acquire: nothing to replace")


async def _replacement_acquire(self) -> None:
    name = _get_name(self)
    _acq_events.append((name, "enter", time.monotonic(), None))
    try:
        async with self._lock:
            now = time.monotonic()

            if now < self._backoff_until:
                wait = self._backoff_until - now
                _acq_events.append((name, "backoff_sleep_attempt", time.monotonic(), wait))
                await asyncio.sleep(wait)
                now = time.monotonic()

            self._tokens = [t for t in self._tokens if now - t < self._window_seconds]

            if len(self._tokens) >= self._max_requests:
                oldest = self._tokens[0]
                wait = self._window_seconds - (now - oldest)
                if wait > 0:
                    _acq_events.append((name, "tokencap_sleep_attempt", time.monotonic(), wait))
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._tokens = [t for t in self._tokens if now - t < self._window_seconds]

            self._tokens.append(time.monotonic())
        _acq_events.append((name, "exit_ok", time.monotonic(), None))
    except BaseException as e:
        _acq_events.append((name, f"exit_err:{type(e).__name__}", time.monotonic(), None))
        raise


def _get_name(limiter) -> str:
    for name, lim in _rl_mod._limiters.items():
        if lim is limiter:
            return name
    return "unknown"
