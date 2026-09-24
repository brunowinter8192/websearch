#!/usr/bin/env python3

# INFRASTRUCTURE

import asyncio
import sys
import tempfile
import time
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import p2_browser_rider as rider_mod
import _p2_watchdog
from p2_browser_rider import RiderState, _abort_stall, _watchdog
from p0_pool import PersistentCooldownManager

_STALL_S = 1.0
_AGED_BY = 200.0
_POLL_S  = 0.1


# ORCHESTRATOR

def main() -> None:
    results = [
        _run_test("test_watchdog_task_fires_and_writes_files", test_watchdog_task_fires_and_writes_files),
        _run_test("test_abort_stall_directly",                  test_abort_stall_directly),
    ]
    passed = sum(results)
    print(f"\n{'='*55}")
    print(f"Results: {passed}/{len(results)} passed")
    if passed < len(results):
        sys.exit(1)


# FUNCTIONS

def _run_test(name: str, fn) -> bool:
    print(f"[test] {name} ...", end=" ", flush=True)
    try:
        fn()
        print("PASS")
        return True
    except AssertionError as exc:
        print(f"FAIL — {exc}")
        return False
    except Exception as exc:
        print(f"ERROR — {exc}")
        return False


def _make_state(tmp_dir: Path, stall_timeout_s: float = _STALL_S) -> RiderState:
    q = asyncio.Queue()
    q.put_nowait("https://www.coindesk.com/test/queued-1")
    q.put_nowait("https://www.coindesk.com/test/queued-2")
    state = RiderState(
        url_queue=q,
        proxy_pool=[],
        cooldown_mgr=PersistentCooldownManager(),
        output_dir=tmp_dir,
        burn_threshold=2,
        page_timeout_ms=8_000,
        total_urls=3,
        stall_timeout_s=stall_timeout_s,
    )
    state.last_progress_mono = time.monotonic() - _AGED_BY
    state.in_flight          = 1
    state.in_flight_urls.add("https://www.coindesk.com/test/inflight-wedged")
    return state


def test_watchdog_task_fires_and_writes_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / rider_mod.RAW_SUBDIR).mkdir()
        exit_calls: list[int] = []

        def fake_exit_1(code: int) -> None:
            raise SystemExit(code)

        async def run() -> None:
            state = _make_state(tmp_dir)
            with unittest.mock.patch.object(_p2_watchdog.os, "_exit", fake_exit_1):
                try:
                    await _watchdog(state, tmp_dir, poll_interval=_POLL_S)
                except SystemExit as exc:
                    exit_calls.append(exc.code)

        asyncio.run(run())

        fail  = tmp_dir / "remaining_urls.txt"
        jobmd = tmp_dir / "job.md"

        assert exit_calls == [1],                        f"os._exit(1) not called: {exit_calls}"
        assert fail.exists(),                            "remaining_urls.txt missing"
        assert jobmd.exists(),                           "job.md missing"

        txt = fail.read_text()
        assert "# never attempted (queue)" in txt,       "queue section header missing"
        assert "# in-flight / wedged at abort" in txt,   "in-flight section header missing"
        assert "queued-1" in txt,                        "queued URL 1 missing"
        assert "queued-2" in txt,                        "queued URL 2 missing"
        assert "inflight-wedged" in txt,                 "in-flight URL missing"

        md = jobmd.read_text()
        assert "stall" in md.lower(),                    "termination=stall missing from job.md"


def test_abort_stall_directly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / rider_mod.RAW_SUBDIR).mkdir()
        exit_calls: list[int] = []

        def fake_exit_2(code: int) -> None:
            raise SystemExit(code)

        async def run() -> None:
            state = _make_state(tmp_dir, stall_timeout_s=60.0)
            with unittest.mock.patch.object(_p2_watchdog.os, "_exit", fake_exit_2):
                try:
                    _abort_stall(state, tmp_dir, idle_s=999.0)
                except SystemExit as exc:
                    exit_calls.append(exc.code)

        asyncio.run(run())

        fail = tmp_dir / "remaining_urls.txt"
        assert exit_calls == [1],                        f"os._exit(1) not called: {exit_calls}"
        assert fail.exists(),                            "remaining_urls.txt missing"
        assert (tmp_dir / "job.md").exists(),            "job.md missing"

        txt = fail.read_text()
        assert "# never attempted (queue)" in txt,       "queue section header missing"
        assert "# in-flight / wedged at abort" in txt,   "in-flight section header missing"
        assert "queued-1" in txt,                        "queued-1 missing"
        assert "inflight-wedged" in txt,                 "in-flight URL missing"
        assert "999" in txt,                             "idle_s not in header"


if __name__ == "__main__":
    main()
