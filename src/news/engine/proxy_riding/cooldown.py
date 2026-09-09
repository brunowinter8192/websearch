# INFRASTRUCTURE

import random
from datetime import datetime, timedelta, timezone

from src.news.engine.proxy_pool.proxy_key import proxy_key

_FIXED_COOLDOWN_S  = 3600
_EXP_BASE_S        = 300
_EXP_CAP_S         = 3600


# ORCHESTRATOR

class RidingCooldownManager:
    def __init__(self, policy: str = "fixed"):
        if policy not in ("fixed", "exp"):
            raise ValueError(f"cooldown policy must be 'fixed' or 'exp', got {policy!r}")
        self._policy           = policy
        self._burned_at:        dict[str, datetime] = {}
        self._next_eligible:    dict[str, datetime] = {}
        self._failed_attempts:  dict[str, int]      = {}

    @property
    def policy(self) -> str:
        return self._policy


# FUNCTIONS

    def mark_burned(self, proto: str, host_port: str, ride_ok: int = 0) -> None:
        key = proxy_key(proto, host_port)
        now = datetime.now(timezone.utc)
        if self._policy == "fixed":
            self._burned_at[key] = now
        else:
            attempts = self._failed_attempts.get(key, 0)
            if ride_ok >= 1:
                attempts = 0
            backoff_s = random.uniform(0, _exp_backoff(attempts))
            self._next_eligible[key]   = now + timedelta(seconds=backoff_s)
            self._failed_attempts[key] = attempts + 1

    def is_eligible(self, proto: str, host_port: str) -> bool:
        key = proxy_key(proto, host_port)
        now = datetime.now(timezone.utc)
        if self._policy == "fixed":
            burned_at = self._burned_at.get(key)
            if burned_at is None:
                return True
            return (now - burned_at) >= timedelta(seconds=_FIXED_COOLDOWN_S)
        else:
            nxt = self._next_eligible.get(key)
            if nxt is None:
                return True
            return now >= nxt

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]

    def cooldown_count(self) -> int:
        now = datetime.now(timezone.utc)
        if self._policy == "fixed":
            return sum(
                1 for dt in self._burned_at.values()
                if (now - dt) < timedelta(seconds=_FIXED_COOLDOWN_S)
            )
        else:
            return sum(1 for nxt in self._next_eligible.values() if now < nxt)

    def earliest_eligible_at(self) -> "datetime | None":
        if self._policy == "fixed":
            if not self._burned_at:
                return None
            return min(self._burned_at.values()) + timedelta(seconds=_FIXED_COOLDOWN_S)
        else:
            if not self._next_eligible:
                return None
            return min(self._next_eligible.values())


def _exp_backoff(attempt: int, cap: float = _EXP_CAP_S, base: float = _EXP_BASE_S) -> float:
    return min(cap, base * (2 ** attempt))
