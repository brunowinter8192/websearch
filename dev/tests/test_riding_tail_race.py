import asyncio
import hashlib
import tempfile
import unittest.mock
from pathlib import Path


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def test_1_surplus_slots_race_both_done() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    urls = ["https://cd.com/a", "https://cd.com/b"]

    async def ok_fetch(crawler, url, proxy_str, page_timeout_ms):
        return "ok", 1000, 500, 0.1, f"<html>{url}</html>", None

    async def fixed_proxy(state):
        return ("http", "p:1")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run():
            q = asyncio.Queue()
            for u in urls:
                q.put_nowait(u)
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=len(urls), target_urls=frozenset(urls),
            )
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", ok_fetch),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                tasks = [asyncio.create_task(rider_mod._run_slot(i, None, state)) for i in range(6)]
                await asyncio.gather(*tasks)
            return state

        state = asyncio.run(run())

        assert state.done_urls == set(urls),   f"done_urls={state.done_urls}"
        assert state.n_ok == 2,                f"n_ok={state.n_ok} (expected 2)"
        for u in urls:
            assert (p / RAW_SUBDIR / f"{_url_hash(u)}.html").exists(), f"raw file missing: {u}"


def test_2_write_exactly_once_per_url() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    url_x = "https://cd.com/x"

    async def ok_fetch(crawler, url, proxy_str, page_timeout_ms):
        return "ok", 1000, 500, 0.1, f"<html>{url}</html>", None

    async def fixed_proxy(state):
        return ("http", "p:1")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run():
            q = asyncio.Queue()
            q.put_nowait(url_x)
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=1, target_urls=frozenset([url_x]),
            )
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", ok_fetch),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                tasks = [asyncio.create_task(rider_mod._run_slot(i, None, state)) for i in range(3)]
                await asyncio.gather(*tasks)
            return state

        state = asyncio.run(run())

        raw_files = list((p / RAW_SUBDIR).iterdir())
        assert state.n_ok == 1,                f"n_ok={state.n_ok} (expected 1)"
        assert state.done_urls == {url_x},     f"done_urls={state.done_urls}"
        assert len(raw_files) == 1,            f"raw file count={len(raw_files)} (expected 1)"


def test_3a_stale_url_skipped() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    url_x = "https://cd.com/stale"
    url_y = "https://cd.com/open"
    fetch_calls: list[str] = []

    async def ok_fetch_spy(crawler, url, proxy_str, page_timeout_ms):
        fetch_calls.append(url)
        return "ok", 1000, 500, 0.1, f"<html>{url}</html>", None

    async def fixed_proxy(state):
        return ("http", "p:1")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run_a():
            q = asyncio.Queue()
            q.put_nowait(url_x)
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=2, target_urls=frozenset([url_x, url_y]),
            )
            state.done_urls.add(url_x)
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", ok_fetch_spy),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                await rider_mod._run_slot(0, None, state)
            return state

        state_a = asyncio.run(run_a())

        assert url_x not in fetch_calls,       f"stale url_x was fetched (should be skipped)"
        assert url_y in fetch_calls,           f"url_y was not fetched"
        assert state_a.done_urls == {url_x, url_y}, f"done_urls={state_a.done_urls}"


def test_3b_raced_fail_not_requeued() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    async def fixed_proxy(state):
        return ("http", "p:1")

    url_x2 = "https://cd.com/race-fail"
    put_calls: list[str] = []
    call_n = [0]

    async def fail_then_ok(crawler, url, proxy_str, page_timeout_ms):
        call_n[0] += 1
        if call_n[0] == 1:
            return "failed", None, None, 0.1, "", "err"
        return "ok", 1000, 500, 0.1, "<html></html>", None

    with tempfile.TemporaryDirectory() as tmp2:
        p2 = Path(tmp2)
        (p2 / RAW_SUBDIR).mkdir()

        async def run_b():
            q = asyncio.Queue()
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p2, job_dir=p2 / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=1, target_urls=frozenset([url_x2]),
            )
            orig_put = state.url_queue.put_nowait
            state.url_queue.put_nowait = lambda u: (put_calls.append(u), orig_put(u))[1]
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", fail_then_ok),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                await rider_mod._run_slot(0, None, state)
            return state

        state_b = asyncio.run(run_b())

        assert url_x2 not in put_calls,        f"raced-fail was re-queued: {put_calls}"
        assert state_b.n_ok == 1,              f"n_ok={state_b.n_ok} (expected 1)"
        assert state_b.done_urls == {url_x2},  f"done_urls={state_b.done_urls}"


def test_4_normal_path_no_racing() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    urls = [f"https://cd.com/{i}" for i in range(4)]
    raced: list[str] = []

    async def ok_fetch(crawler, url, proxy_str, page_timeout_ms):
        return "ok", 1000, 500, 0.1, f"<html>{url}</html>", None

    async def fixed_proxy(state):
        return ("http", "p:1")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run():
            q = asyncio.Queue()
            for u in urls:
                q.put_nowait(u)
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=len(urls), target_urls=frozenset(urls),
            )
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", ok_fetch),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                tasks = [asyncio.create_task(rider_mod._run_slot(i, None, state)) for i in range(4)]
                await asyncio.gather(*tasks)
            return state

        state = asyncio.run(run())

        assert state.n_ok == 4,               f"n_ok={state.n_ok} (expected 4)"
        assert state.done_urls == set(urls),  f"done_urls mismatch"
        raw_files = list((p / RAW_SUBDIR).iterdir())
        assert len(raw_files) == 4,           f"raw file count={len(raw_files)} (expected 4)"


def test_5_fail_before_success_done_once() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.state import RiderState, RAW_SUBDIR
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager as PersistentCooldownManager

    url_x = "https://cd.com/stubborn"
    call_n = [0]

    async def fail_then_ok(crawler, url, proxy_str, page_timeout_ms):
        call_n[0] += 1
        if call_n[0] == 1:
            return "failed", None, None, 0.1, "", "transient error"
        return "ok", 1000, 500, 0.1, "<html>body</html>", None

    async def fixed_proxy(state):
        return ("http", "p:1")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / RAW_SUBDIR).mkdir()

        async def run():
            q = asyncio.Queue()
            q.put_nowait(url_x)
            state = RiderState(
                url_queue=q, proxy_pool=[("http", "p:1")],
                cooldown_mgr=PersistentCooldownManager(),
                output_dir=p, job_dir=p / "jobs",
                burn_threshold=10, page_timeout_ms=8000,
                total_urls=1, target_urls=frozenset([url_x]),
            )
            with (
                unittest.mock.patch.object(rider_mod, "_fetch_one_url", fail_then_ok),
                unittest.mock.patch.object(rider_mod, "_next_proxy",    fixed_proxy),
            ):
                await rider_mod._run_slot(0, None, state)
            return state

        state = asyncio.run(run())

        assert call_n[0] == 2,                f"fetch called {call_n[0]} times (expected 2)"
        assert state.n_ok == 1,               f"n_ok={state.n_ok} (expected 1)"
        assert state.done_urls == {url_x},    f"done_urls={state.done_urls}"
        raw_files = list((p / RAW_SUBDIR).iterdir())
        assert len(raw_files) == 1,           f"raw file count={len(raw_files)} (expected 1)"

