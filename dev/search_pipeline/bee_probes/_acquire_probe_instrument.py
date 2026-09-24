# INFRASTRUCTURE
import asyncio
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

_rl_mod = importlib.import_module("src.search.rate_limiter")
RateLimiter = _rl_mod.RateLimiter

_acq_events: list[tuple[str, str, float]] = []


# FUNCTIONS

def _get_name(limiter) -> str:
    for name, lim in _rl_mod._limiters.items():
        if lim is limiter:
            return name
    return "unknown"


class _WatchedLock:
    def __init__(self, real: asyncio.Lock, limiter) -> None:
        self._real = real
        self._limiter = limiter

    def locked(self) -> bool:
        return self._real.locked()

    async def __aenter__(self):
        name = _get_name(self._limiter)
        _acq_events.append((name, "lock_attempt", time.monotonic()))
        await self._real.__aenter__()
        _acq_events.append((name, "lock_granted", time.monotonic()))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        result = await self._real.__aexit__(exc_type, exc_val, exc_tb)
        evt = "lock_stuck" if self._real.locked() else "lock_released"
        _acq_events.append((_get_name(self._limiter), evt, time.monotonic()))
        return result


_orig_init = RateLimiter.__init__


def _patched_init(self, *args, **kwargs) -> None:
    _orig_init(self, *args, **kwargs)
    self._lock = _WatchedLock(self._lock, self)


_orig_acquire = RateLimiter.acquire


async def _patched_acquire(self) -> None:
    name = _get_name(self)
    _acq_events.append((name, "enter", time.monotonic()))
    try:
        await _orig_acquire(self)
        _acq_events.append((name, "exit_ok", time.monotonic()))
    except BaseException as e:
        _acq_events.append((name, f"exit_err:{type(e).__name__}", time.monotonic()))
        raise


RateLimiter.__init__ = _patched_init
RateLimiter.acquire = _patched_acquire
