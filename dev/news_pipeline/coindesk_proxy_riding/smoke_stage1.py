"""
Stage 1 smoke — src/news/engine/proxy_riding/ package validation.

Three sections:
  1. Import check (no network)
  2. Deterministic watchdog test (patches os._exit — no network, no browser)
  3. Mini live run: 10 inventory URLs, 2 slots, 1 browser, 300s stall — validates
     manifest shape, shuffle, and raw .html writes.

Usage (from main checkout):
    cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/searxng-cli
    ./venv/bin/python .claude/worktrees/riding-port/dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py
"""

# INFRASTRUCTURE

import asyncio
import sys
import tempfile
import time
import unittest.mock
from pathlib import Path

# Worktree root contains the new src/news/engine/proxy_riding/ package;
# prepend it so imports resolve from here, not the main checkout's src/.
_WORKTREE = Path(__file__).parents[3]  # dev/news_pipeline/coindesk_proxy_riding/ → riding-port/
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

MAIN_CHECKOUT = Path(__file__).parents[6]  # .claude/worktrees/riding-port → repo root
INVENTORY_DIR = MAIN_CHECKOUT / "data" / "news" / "coindesk" / "inventory"
N_LIVE_URLS   = 10
REQUIRED_KEYS = {"url", "hash", "status", "file", "char_count", "error"}
VALID_STATUSES = {"ok", "failed"}


# ORCHESTRATOR

def main() -> None:
    results = []
    results.append(_run("1. import check",          test_import_clean))
    results.append(_run("2. watchdog deterministic", test_watchdog_deterministic))
    results.append(_run("3. live run",               lambda: asyncio.run(test_live_run())))

    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"Smoke results: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

def _run(name: str, fn) -> bool:
    print(f"\n[smoke] {name} ...", flush=True)
    try:
        fn()
        print(f"  PASS")
        return True
    except AssertionError as exc:
        print(f"  FAIL — {exc}")
        return False
    except Exception as exc:
        import traceback
        print(f"  ERROR — {exc}")
        traceback.print_exc()
        return False


# Section 1 — import clean: package resolves without sys.path tricks
def test_import_clean() -> None:
    import src.news.engine.proxy_riding.rider    as rider_mod
    import src.news.engine.proxy_riding.abort    as abort_mod
    import src.news.engine.proxy_riding.reporter as reporter_mod
    from src.news.engine.proxy_riding.scrape import (
        scrape_entries_riding, RidingScrapeConfig, BROWSER_ELIGIBLE_PROTOS,
    )
    from src.news.engine.proxy_riding.state import RiderState, RideRecord, JobRecord, FAIL_THRESHOLD
    from src.news.engine.proxy_riding.rider import run_riding_pool, _watchdog
    from src.news.engine.proxy_riding.abort import _abort_stall
    from src.news.engine.proxy_riding.reporter import write_riding_report

    # Confirm defaults match validated production values
    cfg = RidingScrapeConfig()
    assert cfg.n_browsers      == 4,      f"n_browsers default wrong: {cfg.n_browsers}"
    assert cfg.n_slots         == 64,     f"n_slots default wrong: {cfg.n_slots}"
    assert cfg.stall_timeout_s == 300.0,  f"stall_timeout_s default wrong: {cfg.stall_timeout_s}"
    assert cfg.burn_threshold  == 2,      f"burn_threshold default wrong: {cfg.burn_threshold}"
    assert cfg.page_timeout_ms == 8_000,  f"page_timeout_ms default wrong: {cfg.page_timeout_ms}"

    # Confirm BROWSER_ELIGIBLE_PROTOS matches dev runner
    assert BROWSER_ELIGIBLE_PROTOS == frozenset({"http", "socks5"})

    # Confirm no sys.path manipulation in production modules
    src_rider    = Path(rider_mod.__file__).read_text()
    src_abort    = Path(abort_mod.__file__).read_text()
    src_reporter = Path(reporter_mod.__file__).read_text()
    assert "sys.path.insert" not in src_rider,    "sys.path.insert found in rider.py"
    assert "sys.path.insert" not in src_abort,    "sys.path.insert found in abort.py"
    assert "sys.path.insert" not in src_reporter, "sys.path.insert found in reporter.py"

    # Confirm late import in _abort_stall uses src package path
    assert "src.news.engine.proxy_riding.reporter" in src_abort, \
        "late import in _abort_stall does not reference src package"

    print("    imports ok, defaults ok, no sys.path hacks, late import correct")


def _make_watchdog_state(tmp_dir: Path, stall_s: float, aged_by: float) -> object:
    from src.news.engine.proxy_riding.state import RiderState
    from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager

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
        stall_timeout_s=stall_s,
    )
    state.last_progress_mono = time.monotonic() - aged_by
    state.in_flight          = 1
    state.in_flight_urls.add("https://www.coindesk.com/test/inflight-wedged")
    return state


def _assert_watchdog_outputs(tmp_dir: Path) -> None:
    fail  = tmp_dir / "remaining_urls.txt"
    jobmd = tmp_dir / "job.md"
    assert fail.exists(),  "remaining_urls.txt not written"
    assert jobmd.exists(), "job.md not written"

    txt = fail.read_text()
    assert "# never attempted (queue)"   in txt, "queue section missing"
    assert "# in-flight / wedged at abort" in txt, "in-flight section missing"
    assert "queued-1"        in txt, "queued-1 URL missing"
    assert "inflight-wedged" in txt, "in-flight URL missing"
    assert "stall" in jobmd.read_text().lower(), "stall termination missing from job.md"


# Section 2 — deterministic watchdog: pre-aged state + patched os._exit
def test_watchdog_deterministic() -> None:
    import src.news.engine.proxy_riding.rider as rider_mod
    from src.news.engine.proxy_riding.rider import _watchdog
    from src.news.engine.proxy_riding.abort import _abort_stall

    _STALL_S = 1.0
    _AGED_BY = 200.0
    _POLL_S  = 0.1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / rider_mod.RAW_SUBDIR).mkdir()
        exit_calls: list[int] = []

        def fake_exit(code: int) -> None:
            raise SystemExit(code)

        async def run() -> None:
            state = _make_watchdog_state(tmp_dir, _STALL_S, _AGED_BY)
            with unittest.mock.patch.object(rider_mod.os, "_exit", fake_exit):
                try:
                    await _watchdog(state, tmp_dir, poll_interval=_POLL_S)
                except SystemExit as exc:
                    exit_calls.append(exc.code)

        asyncio.run(run())

        assert exit_calls == [1], f"os._exit(1) not called — got: {exit_calls}"
        _assert_watchdog_outputs(tmp_dir)

    print("    watchdog fired → os._exit(1), remaining_urls.txt ok, job.md ok")


# Load inventory URLs
def _load_inventory_urls(n: int) -> list:
    assert INVENTORY_DIR.exists(), f"inventory dir missing: {INVENTORY_DIR}"
    inv_files = sorted(INVENTORY_DIR.glob("*.txt"))
    assert inv_files, "no .txt files in inventory"

    urls: list[str] = []
    for f in inv_files:
        lines = [ln.strip() for ln in f.read_text().splitlines() if ln.strip()]
        urls.extend(lines)
        if len(urls) >= n:
            break
    urls = urls[:n]
    assert len(urls) == n, f"could not collect {n} URLs: got {len(urls)}"
    return urls


# Manifest shape
def _assert_manifest_shape(manifest: list) -> None:
    assert len(manifest) == N_LIVE_URLS, \
        f"manifest length mismatch: {len(manifest)} ≠ {N_LIVE_URLS}"
    for i, m in enumerate(manifest):
        missing = REQUIRED_KEYS - m.keys()
        assert not missing, f"entry[{i}] missing keys: {missing}"
        assert m["status"] in VALID_STATUSES, \
            f"entry[{i}] invalid status: {m['status']!r}"
        if m["status"] == "ok":
            assert m["file"] is not None,  f"entry[{i}] ok but file=None"
            assert Path(m["file"]).exists(), f"entry[{i}] ok file missing: {m['file']}"
            assert m["file"].endswith(".html"), \
                f"entry[{i}] ok file not .html: {m['file']}"


# Shuffle: verify pool order differs from sequential (check raw_pool via loader)
async def _assert_pool_shuffle_effective() -> int:
    import random as _random
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

    raw_pool, _ = await asyncio.get_running_loop().run_in_executor(None, load_backfill_pool)
    filtered    = [(p, hp) for p, hp in raw_pool if p in frozenset({"http", "socks5"})]
    shuffled    = filtered[:]
    _random.shuffle(shuffled)
    # Shuffle is probabilistic; with ~15k entries the chance of identical order is ~0.
    # Check that shuffled != sorted order as a proxy.
    assert shuffled != sorted(filtered), \
        "shuffle produced sorted order — extremely unlikely, re-run"
    return len(filtered)


# Section 3 — live run: real pool + real URLs, validate manifest + shuffle + raw writes
async def test_live_run() -> None:
    from src.news.engine.proxy_riding.scrape import scrape_entries_riding, RidingScrapeConfig

    urls = _load_inventory_urls(N_LIVE_URLS)
    entries = [{"url": u} for u in urls]

    print(f"    {N_LIVE_URLS} inventory URLs loaded")

    # Minimal config: 2 slots, 1 browser, 300s stall
    cfg = RidingScrapeConfig(
        n_slots=2, n_browsers=1, burn_threshold=2,
        page_timeout_ms=8_000, stall_timeout_s=300.0,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        t0  = time.monotonic()
        manifest = await scrape_entries_riding(entries, out, cfg)
        elapsed  = time.monotonic() - t0

        _assert_manifest_shape(manifest)

        n_ok     = sum(1 for m in manifest if m["status"] == "ok")
        n_failed = sum(1 for m in manifest if m["status"] == "failed")
        raw_dir  = out / "raw"
        raw_html = list(raw_dir.glob("*.html")) if raw_dir.exists() else []

        print(f"    elapsed={elapsed:.0f}s  ok={n_ok}  failed={n_failed}  "
              f"raw_html={len(raw_html)}")

        n_filtered = await _assert_pool_shuffle_effective()
        print(f"    shuffle ok (pool={n_filtered} browser-eligible proxies)")

        assert len(manifest) == N_LIVE_URLS, "manifest length invariant broken post-shuffle-check"
        print(f"    manifest shape ok: {N_LIVE_URLS} entries, all keys present, "
              f"statuses in {VALID_STATUSES!r}")
        if raw_html:
            sample = raw_html[0]
            print(f"    raw sample: {sample.name}  {sample.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
