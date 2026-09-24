from datetime import datetime, timedelta, timezone

_PROTO = "http"
_HP    = "proxy:8080"


def _burn_at_offset(mgr, proto, hp, offset_s: float, ride_ok: int = 0) -> None:
    from src.news.engine.proxy_pool.proxy_key import proxy_key
    mgr.mark_burned(proto, hp, ride_ok=ride_ok)
    key = proxy_key(proto, hp)
    now = datetime.now(timezone.utc)
    if mgr._policy == "fixed":
        mgr._burned_at[key] = now - timedelta(seconds=offset_s)
    else:
        mgr._next_eligible[key] = now - timedelta(seconds=offset_s)


def test_fixed_60min() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    mgr = RidingCooldownManager(policy="fixed")

    _burn_at_offset(mgr, _PROTO, _HP, offset_s=59 * 60)
    assert not mgr.is_eligible(_PROTO, _HP), "should still be in cooldown at t+59min"

    _burn_at_offset(mgr, _PROTO, _HP, offset_s=61 * 60)
    assert mgr.is_eligible(_PROTO, _HP),     "should be eligible after 60min cooldown"


def test_fixed_default_equiv() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    mgr = RidingCooldownManager()
    assert mgr._policy == "fixed", f"default policy should be 'fixed', got {mgr._policy!r}"
    _burn_at_offset(mgr, _PROTO, _HP, offset_s=59 * 60)
    assert not mgr.is_eligible(_PROTO, _HP), "default should enforce 60-min cooldown"


def test_exp_unproductive_bounds() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    BASE = 300.0

    for n in range(3):
        t_before = datetime.now(timezone.utc)
        mgr.mark_burned(_PROTO, _HP, ride_ok=0)
        t_after  = datetime.now(timezone.utc)

        key = proxy_key(_PROTO, _HP)
        nxt = mgr._next_eligible[key]

        upper = t_before + timedelta(seconds=_exp_backoff(n, base=BASE))
        assert nxt >= t_before,  f"burn {n}: next_eligible {nxt} before burn time {t_before}"
        assert nxt <= upper + timedelta(seconds=1),  \
            f"burn {n}: next_eligible exceeds upper bound base*2**{n}={_exp_backoff(n,base=BASE):.0f}s"

        assert not mgr.is_eligible(_PROTO, _HP), f"burn {n}: proxy should be in cooldown"


def test_exp_cap() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    CAP = 3600.0

    for _ in range(20):
        mgr.mark_burned(_PROTO, _HP, ride_ok=0)

    key = proxy_key(_PROTO, _HP)
    nxt = mgr._next_eligible[key]
    now = datetime.now(timezone.utc)
    gap_s = (nxt - now).total_seconds()
    assert gap_s <= CAP + 1, f"backoff {gap_s:.0f}s exceeds cap {CAP}s"


def test_exp_reset_on_productive() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr  = RidingCooldownManager(policy="exp")
    BASE = 300.0
    key  = proxy_key(_PROTO, _HP)

    mgr.mark_burned(_PROTO, _HP, ride_ok=0)
    mgr.mark_burned(_PROTO, _HP, ride_ok=0)
    t_before = datetime.now(timezone.utc)
    mgr.mark_burned(_PROTO, _HP, ride_ok=1)
    upper = t_before + timedelta(seconds=_exp_backoff(0, base=BASE))
    nxt   = mgr._next_eligible[key]
    assert nxt <= upper + timedelta(seconds=1), \
        f"reset not applied: next_eligible gap {(nxt - t_before).total_seconds():.0f}s > base {BASE}s"

    assert mgr._failed_attempts[key] == 1, \
        f"expected failed_attempts=1 after reset+burn, got {mgr._failed_attempts[key]}"


def test_exp_eligible_after_backoff() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    mgr.mark_burned(_PROTO, _HP, ride_ok=0)

    key = proxy_key(_PROTO, _HP)
    assert not mgr.is_eligible(_PROTO, _HP), "should be in cooldown immediately after burn"

    mgr._next_eligible[key] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert mgr.is_eligible(_PROTO, _HP), "should be eligible once next_eligible has passed"


def test_exp_cooldown_count() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    N    = 4
    mgr  = RidingCooldownManager(policy="exp")
    pool = [(_PROTO, f"proxy:{i}") for i in range(N)]

    for proto, hp in pool:
        mgr.mark_burned(proto, hp, ride_ok=0)

    assert mgr.cooldown_count() == N, \
        f"expected cooldown_count={N} after {N} burns, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 0, \
        "all proxies should be ineligible immediately after burn"

    now = datetime.now(timezone.utc)
    for proto, hp in pool:
        mgr._next_eligible[proxy_key(proto, hp)] = now - timedelta(seconds=1)

    assert mgr.cooldown_count() == 0, \
        f"expected cooldown_count=0 after backdating, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == N, \
        f"expected all {N} eligible after backdating"


def test_fixed_cooldown_count() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager

    mgr  = RidingCooldownManager(policy="fixed")
    pool = [(_PROTO, f"proxy:{i}") for i in range(3)]

    for proto, hp in pool:
        mgr.mark_burned(proto, hp)

    assert mgr.cooldown_count() == 3, \
        f"expected 3 in cooldown immediately after burns, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 0, "all should be in cooldown"

    _burn_at_offset(mgr, _PROTO, "proxy:0", offset_s=3601)
    _burn_at_offset(mgr, _PROTO, "proxy:1", offset_s=3601)

    assert mgr.cooldown_count() == 1, \
        f"expected 1 in cooldown after backdating two, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 2, \
        f"expected 2 eligible after backdating two"

