#!/usr/bin/env python3
"""
Deterministic SIGINT/SIGTERM report tests for src/news/engine/proxy_riding/rider.py.
No browser or proxy infrastructure needed.

test 1 — _abort_interrupted SIGINT: constructs RiderState with partial job data,
         patches os._exit to raise SystemExit, calls _abort_interrupted directly,
         asserts exit code 130, job.md + cumulative.png written, termination=interrupted.

test 2 — _abort_interrupted SIGTERM: same but with signal.SIGTERM → exit code 143.

All src/ imports are lazy (inside function bodies) to satisfy dev/ isolation rules.

Usage:
    ./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_sigint_report.py
"""

# INFRASTRUCTURE

import asyncio
import signal
import sys
import tempfile
import time
import unittest.mock
from pathlib import Path

# Prepend worktree root so lazy src/ imports inside function bodies resolve correctly.
_WORKTREE = Path(__file__).parents[3]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))


# ORCHESTRATOR

def main() -> None:
    results = [
        _run("test_abort_interrupted_sigint",  test_abort_interrupted_sigint),
        _run("test_abort_interrupted_sigterm", test_abort_interrupted_sigterm),
    ]
    passed = sum(results)
    print(f"\n{'='*55}")
    print(f"Results: {passed}/{len(results)} passed")
    if passed < len(results):
        sys.exit(1)


# FUNCTIONS

def _run(name: str, fn) -> bool:
    print(f"[test] {name} ...", end=" ", flush=True)
    try:
        fn()
        print("PASS")
        return True
    except AssertionError as exc:
        print(f"FAIL — {exc}")
        return False
    except Exception as exc:
        import traceback
        print(f"ERROR — {exc}")
        traceback.print_exc()
        return False


def _build_job_records(t0, tmp_dir: Path) -> list:
    from src.news.engine.proxy_riding.state import JobRecord

    records = []
    for i, url in enumerate(["https://www.coindesk.com/test/ok-1",
                              "https://www.coindesk.com/test/ok-2"]):
        records.append(JobRecord(
            url=url,
            url_hash=f"aabbcc{i:06d}",
            status="ok",
            char_count=5000,
            markdown_len=2000,
            elapsed_s=1.5,
            error=None,
            file=str(tmp_dir / "raw" / f"aabbcc{i:06d}.html"),
            t_start=t0,
            ride_position=i + 1,
            proxy_str="http://proxy:8080",
        ))
    return records


def _build_ride_record() -> object:
    from src.news.engine.proxy_riding.state import RideRecord

    return RideRecord(
        proxy_str="http://proxy:8080",
        proto="http",
        host_port="proxy:8080",
        n_ok=2,
        n_regwall=1,
        n_connect_fail=0,
        n_failed=0,
        n_urls_attempted=3,
        burned_threshold=False,
        burned_connect=False,
        ride_s=4.5,
        positions=[],
    )


# Build a minimal RiderState with two resolved job records so reporter has data.
def _make_state(tmp_dir: Path) -> object:
    from src.news.engine.proxy_riding.state import RiderState
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    from datetime import datetime, timezone

    job_dir = tmp_dir / "scrape_jobs" / "20250101T000000Z"
    q = asyncio.Queue()
    q.put_nowait("https://www.coindesk.com/test/pending-1")

    state = RiderState(
        url_queue=q,
        proxy_pool=[("http", "proxy:8080")],
        cooldown_mgr=RidingCooldownManager(),
        output_dir=tmp_dir,
        job_dir=job_dir,
        burn_threshold=2,
        page_timeout_ms=8_000,
        total_urls=3,
        target_urls=frozenset([
            "https://www.coindesk.com/test/ok-1",
            "https://www.coindesk.com/test/ok-2",
            "https://www.coindesk.com/test/pending-1",
        ]),
        stall_timeout_s=3600.0,
    )
    state.n_browsers = 1
    state.n_slots    = 4
    state.n_ok       = 2
    state.n_regwall  = 1
    state.n_failed   = 0
    state.n_connect_fail = 0
    state.last_progress_mono = time.monotonic()

    t0 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    state.t_job_start = t0

    state.job_records.extend(_build_job_records(t0, tmp_dir))
    state.done_urls = {
        "https://www.coindesk.com/test/ok-1",
        "https://www.coindesk.com/test/ok-2",
    }

    state.ride_records.append(_build_ride_record())

    state.pool_samples = [(30.0, 500, 10), (60.0, 480, 30)]
    return state


# _abort_interrupted(SIGINT): report written, exit 130, termination=interrupted.
def test_abort_interrupted_sigint() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.abort import _abort_interrupted

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "raw").mkdir()
        exit_calls: list[int] = []

        def fake_exit(code: int) -> None:
            raise SystemExit(code)

        async def run() -> None:
            state = _make_state(tmp_dir)
            with unittest.mock.patch.object(rider_mod.os, "_exit", fake_exit):
                try:
                    _abort_interrupted(state, signal.SIGINT)
                except SystemExit as exc:
                    exit_calls.append(exc.code)
            return state

        state = asyncio.run(run())

        job_dir = tmp_dir / "scrape_jobs" / "20250101T000000Z"

        assert exit_calls == [130],              f"expected os._exit(130), got {exit_calls}"
        assert (job_dir / "job.md").exists(),    "job.md not written"
        assert (job_dir / "cumulative.png").exists(), "cumulative.png not written"
        assert state.termination == "interrupted", f"termination={state.termination!r}"

        md = (job_dir / "job.md").read_text()
        assert "interrupted" in md.lower(),      "termination=interrupted missing from job.md"


# _abort_interrupted(SIGTERM): exit 143, same files.
def test_abort_interrupted_sigterm() -> None:
    from src.news.engine.proxy_riding import rider as rider_mod
    from src.news.engine.proxy_riding.abort import _abort_interrupted

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "raw").mkdir()
        exit_calls: list[int] = []

        def fake_exit(code: int) -> None:
            raise SystemExit(code)

        async def run() -> None:
            state = _make_state(tmp_dir)
            with unittest.mock.patch.object(rider_mod.os, "_exit", fake_exit):
                try:
                    _abort_interrupted(state, signal.SIGTERM)
                except SystemExit as exc:
                    exit_calls.append(exc.code)
            return state

        state = asyncio.run(run())

        job_dir = tmp_dir / "scrape_jobs" / "20250101T000000Z"

        assert exit_calls == [143],              f"expected os._exit(143), got {exit_calls}"
        assert (job_dir / "job.md").exists(),    "job.md not written"
        assert (job_dir / "cumulative.png").exists(), "cumulative.png not written"
        assert state.termination == "interrupted", f"termination={state.termination!r}"

        md = (job_dir / "job.md").read_text()
        assert "interrupted" in md.lower(),      "termination=interrupted missing from job.md"


if __name__ == "__main__":
    main()
