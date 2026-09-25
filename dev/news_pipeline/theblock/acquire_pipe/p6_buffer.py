# INFRASTRUCTURE
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import proxy_key

sys.path.insert(0, str(Path(__file__).parent))
from p2_cooldown import PersistentCooldownManager

BUFFER_SIZE        = 1280
DEFAULT_CONCURRENCY = 128


# FUNCTIONS

def build_active_buffer(
    pool_22k: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    max_size: int = BUFFER_SIZE,
) -> list[tuple[str, str]]:
    eligible = cm.eligible_candidates(pool_22k)
    return eligible[:max_size]


def refill_buffer(
    buf: list[tuple[str, str]],
    pool_22k: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    target_size: int = BUFFER_SIZE,
) -> list[tuple[str, str]]:
    if len(buf) >= target_size:
        return buf
    in_buf   = set(buf)
    eligible = cm.eligible_candidates(pool_22k)
    additions = [p for p in eligible if p not in in_buf]
    needed    = target_size - len(buf)
    return buf + additions[:needed]
