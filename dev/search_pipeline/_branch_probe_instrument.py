# INFRASTRUCTURE
import asyncio
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Monkey-patch RateLimiter.acquire BEFORE any src.search imports.
# Full replacement (not wrapper) — byte-identical body to rate_limiter.py:acquire()
# with branch-discriminator event-emits before each asyncio.sleep.
_rl_mod = importlib.import_module("src.search.rate_limiter")
RateLimiter = _rl_mod.RateLimiter

# (engine_name, event, ts_monotonic, wait_s_or_None)
_acq_events: list[tuple[str, str, float, float | None]] = []

# per-query pre-call snapshots: list of {qi, engines: {name -> {backoff_remaining_s, len_tokens, ...}}}
_pre_snapshots: list[dict] = []


# FUNCTIONS

def _get_name(limiter) -> str:
    """Reverse-lookup engine name from _limiters dict by instance identity."""
    for name, lim in _rl_mod._limiters.items():
        if lim is limiter:
            return name
    return "unknown"


async def _replacement_acquire(self) -> None:
    """Byte-identical to rate_limiter.py:acquire() + branch-discriminator event-emits."""
    name = _get_name(self)
    _acq_events.append((name, "enter", time.monotonic(), None))
    try:
        async with self._lock:
            now = time.monotonic()

            # Respect backoff from 429/403 responses
            if now < self._backoff_until:
                wait = self._backoff_until - now
                _acq_events.append((name, "backoff_sleep_attempt", time.monotonic(), wait))
                await asyncio.sleep(wait)
                now = time.monotonic()

            # Remove tokens older than the window
            self._tokens = [t for t in self._tokens if now - t < self._window_seconds]

            # If at capacity, wait until the oldest token expires
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


RateLimiter.acquire = _replacement_acquire
