# INFRASTRUCTURE

from src.config import PROXY_POOL_BUFFER_SIZE
from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager


# FUNCTIONS

def build_active_buffer(
    pool: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    max_size: int = PROXY_POOL_BUFFER_SIZE,
) -> list[tuple[str, str]]:
    eligible = cm.eligible_candidates(pool)
    return eligible[:max_size]


def refill_buffer(
    buf: list[tuple[str, str]],
    pool: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    target_size: int = PROXY_POOL_BUFFER_SIZE,
) -> list[tuple[str, str]]:
    if len(buf) >= target_size:
        return buf
    in_buf    = set(buf)
    eligible  = cm.eligible_candidates(pool)
    additions = [p for p in eligible if p not in in_buf]
    needed    = target_size - len(buf)
    return buf + additions[:needed]
