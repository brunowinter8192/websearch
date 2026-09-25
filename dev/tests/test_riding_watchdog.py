# INFRASTRUCTURE
import asyncio
import os
import tempfile
import unittest.mock
from pathlib import Path


# FUNCTIONS

def test_6_watchdog_wedge_after_all_resolved() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.config import RAW_SUBDIR
    from src.news.engine.proxy_riding.state import RiderState
    from src.news.engine.proxy_riding.rider import _watchdog
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    url_done = "https://cd.com/already-done"
    exit_calls: list[int] = []

    def fake_exit(code: int) -> None:
        exit_calls.append(code)
        raise SystemExit(code)

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run() -> RiderState:
            q = asyncio.Queue()
            state = RiderState(
                url_queue=q, proxy_pool=[],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=2, page_timeout_ms=8_000,
                total_urls=1, target_urls=frozenset([url_done]),
            )
            state.done_urls.add(url_done)
            state.in_flight = 1

            with (
                unittest.mock.patch.object(os, "_exit", fake_exit),
                unittest.mock.patch("src.news.engine.proxy_riding.reporter.write_riding_report"),
            ):
                try:
                    await _watchdog(state, poll_interval=0.1)
                except SystemExit:
                    return state
            return state

        state = asyncio.run(run())

    assert exit_calls == [0],               f"expected os._exit(0), got {exit_calls}"
    assert state.termination == "all-done", f"termination={state.termination!r}"


def test_7_watchdog_pool_refresh() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.config import RAW_SUBDIR
    from src.news.engine.proxy_riding.state import RiderState
    from src.news.engine.proxy_riding.rider import _watchdog
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    pool_a = [("http", "proxy-a1:1"), ("http", "proxy-a2:2")]
    pool_b = [("http", "proxy-b1:1"), ("socks5", "proxy-b2:2"), ("http", "proxy-b3:3")]
    refresh_count = [0]

    async def mock_provider() -> list:
        refresh_count[0] += 1
        return pool_b

    url_done = "https://cd.com/refreshed"

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run():
            q = asyncio.Queue()
            state = RiderState(
                url_queue=q, proxy_pool=pool_a,
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=2, page_timeout_ms=8_000,
                total_urls=1, target_urls=frozenset([url_done]),
                pool_provider=mock_provider,
            )
            state.done_urls.add(url_done)

            with unittest.mock.patch.object(rider_mod, "RIDING_POOL_REFRESH_INTERVAL_S", 0.0):
                await _watchdog(state, poll_interval=0.05)
            return state

        state = asyncio.run(run())

    assert refresh_count[0] >= 1,      f"pool_provider not called (refresh_count={refresh_count[0]})"
    assert state.proxy_pool is pool_b, f"proxy_pool not replaced: {state.proxy_pool}"
