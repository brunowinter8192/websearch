# INFRASTRUCTURE
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import proxy_key

COOLDOWN_S = 3600


# FUNCTIONS

class PersistentCooldownManager:

    def __init__(self, cooldown_s: int = COOLDOWN_S):
        self._cooldown_td = timedelta(seconds=cooldown_s)
        self._burned_utc: dict[str, datetime] = {}

    def mark_burned(self, proto: str, host_port: str) -> None:
        key = proxy_key(proto, host_port)
        self._burned_utc[key] = datetime.now(timezone.utc)

    def is_eligible(self, proto: str, host_port: str) -> bool:
        burned_at = self._burned_utc.get(proxy_key(proto, host_port))
        if burned_at is None:
            return True
        return (datetime.now(timezone.utc) - burned_at) >= self._cooldown_td

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]

    def cooldown_count(self) -> int:
        now = datetime.now(timezone.utc)
        return sum(1 for dt in self._burned_utc.values() if (now - dt) < self._cooldown_td)

    def earliest_eligible_at(self) -> "datetime | None":
        if not self._burned_utc:
            return None
        return min(self._burned_utc.values()) + self._cooldown_td
