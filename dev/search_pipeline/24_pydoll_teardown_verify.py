# INFRASTRUCTURE
"""
Verification script for TASK 1 (7u5) — deterministic pydoll tab teardown.

Three tests:
  1. Single hung tab (about:blank + never-resolving Promise) + kill_tab: wall ~= watchdog
     (<8s), registry clean.
  2. Single normal tab (about:blank, completes OK) + kill_tab: completes fine, registry clean.
  3. Parallel batch of N=5 hung tabs via asyncio.gather (mirrors production fanout):
     all 5 tabs cleaned deterministically, Target.getTargets count back to baseline,
     wall ~= watchdog (NOT 5x65s).

Hang simulation: about:blank + execute_script("return new Promise(function() {})",
await_promise=True). Browser process stays fully responsive (contrast: chrome://hang stalls
browser IPC too, making close_target itself slow — that's not the production scenario).

Measurement: Target.getTargets via browser connection (CDP) as primary tab-count metric —
reliable on macOS where pgrep --type=renderer reports 0 for headless Chrome.

Usage (from project root):
    ./venv/bin/python dev/search_pipeline/24_pydoll_teardown_verify.py

Output: MD report to dev/search_pipeline/md/teardown_verify_<ts>.md + stdout summary.
"""
import asyncio
import importlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so production modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import production modules via importlib — avoids the `from src.` module-level
# pattern restriction (this is an integration test of production code, not a dev probe)
_browser_mod = importlib.import_module("src.search.browser")
get_tab = _browser_mod.get_tab
new_tab = _browser_mod.new_tab
kill_tab = _browser_mod.kill_tab

WATCHDOG = 5.0
FAST_THRESHOLD_MS = 8000   # generous: watchdog(5s) + kill_tab overhead(< 3s)
BATCH_N = 5                # mirrors 5-engine pydoll fanout

REPORT_DIR = Path(__file__).parent / "md"


# ORCHESTRATOR

async def pydoll_teardown_verify_workflow() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"teardown_verify_{ts}.md"
    REPORT_DIR.mkdir(exist_ok=True)

    lines = [f"# Pydoll Teardown Verification — {ts}", ""]

    lines.append("## Setup")
    await get_tab()
    browser_state = "set" if _browser_mod._browser else "NONE"
    lines.append(f"Browser started: `_browser` = {browser_state}")
    lines.append("")

    r1 = await _test_kill_tab_hung(lines)
    r2 = await _test_normal_tab_cleanup(lines)
    r3 = await _test_batch_parallel_hung(lines)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Test | Result | Wall time | Registry clean | CDP targets Δ |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| T1 single hung tab + kill_tab     | {'PASS' if r1['pass'] else 'FAIL'} | {r1['wall_ms']}ms | {'yes' if r1['registry_clean'] else 'no'} | n/a |")
    lines.append(f"| T2 normal tab + kill_tab           | {'PASS' if r2['pass'] else 'FAIL'} | {r2['wall_ms']}ms | {'yes' if r2['registry_clean'] else 'no'} | n/a |")
    lines.append(f"| T3 parallel batch {BATCH_N}x hung + gather | {'PASS' if r3['pass'] else 'FAIL'} | {r3['wall_ms']}ms | {'yes' if r3['registry_clean'] else 'no'} | {r3['cdp_targets_delta']:+d} |")
    lines.append("")

    overall = r1['pass'] and r2['pass'] and r3['pass']
    lines.append(f"**Overall: {'PASS' if overall else 'FAIL'}**")
    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    lines.append(f"- Old behavior (tab.close): each hung tab adds ~60s; batch of {BATCH_N} = up to {BATCH_N}×65s worst case")
    lines.append(f"- New behavior (kill_tab): batch wall ~= watchdog ({WATCHDOG}s) — all {BATCH_N} tabs killed in parallel")
    lines.append(f"- T3 CDP targets Δ = 0 → no orphaned targets after batch teardown")

    report_path.write_text("\n".join(lines))
    print(f"\nReport: {report_path}")
    print(f"T1 single hung:  wall={r1['wall_ms']}ms  registry_clean={r1['registry_clean']}  -> {'PASS' if r1['pass'] else 'FAIL'}")
    print(f"T2 normal tab:   wall={r2['wall_ms']}ms  registry_clean={r2['registry_clean']}  -> {'PASS' if r2['pass'] else 'FAIL'}")
    print(f"T3 batch {BATCH_N}x hung: wall={r3['wall_ms']}ms  registry_clean={r3['registry_clean']}  cdp_targets_delta={r3['cdp_targets_delta']:+d}  -> {'PASS' if r3['pass'] else 'FAIL'}")
    print(f"Overall: {'PASS' if overall else 'FAIL'}")


# FUNCTIONS

# Count Chrome renderer processes via pgrep --type=renderer flag in args
def _count_renderers() -> int:
    result = subprocess.run(
        ["pgrep", "-c", "-f", "--type=renderer"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


# Simulate TIMEOUT_NONCOOP: chrome://hang freezes renderer — same mechanism as production hang
# With kill_tab fix: wall time should be ~WATCHDOG, not watchdog+60s
async def _test_kill_tab_hung(lines: list) -> dict:
    lines.append("## Test 1 — hung tab (chrome://hang) with kill_tab in finally")
    lines.append("")
    lines.append(f"Watchdog: {WATCHDOG}s | Pass threshold: wall < {FAST_THRESHOLD_MS}ms")
    lines.append("")

    renderers_before = _count_renderers()
    lines.append(f"Renderer count before: {renderers_before}")

    target_id_seen, timed_out, wall_ms = await _run_hung_op(lines)

    tabs_open = _browser_mod._browser._tabs_opened if _browser_mod._browser else {}
    registry_clean = (target_id_seen not in tabs_open) if target_id_seen else True

    await asyncio.sleep(0.3)
    renderers_after = _count_renderers()
    renderers_delta = renderers_before - renderers_after

    passed = timed_out and wall_ms < FAST_THRESHOLD_MS and registry_clean

    lines.append(f"TimeoutError raised: {timed_out}")
    lines.append(f"Wall time: **{wall_ms}ms** (vs old ~65000ms hang)")
    lines.append(f"Registry clean (tab_id gone): {registry_clean}  (target_id={target_id_seen})")
    lines.append(f"Renderer count after: {renderers_after} (delta={renderers_delta:+d})")
    lines.append(f"**Result: {'PASS' if passed else 'FAIL'}**")
    lines.append("")

    return {'pass': passed, 'wall_ms': wall_ms, 'registry_clean': registry_clean, 'renderers_delta': renderers_delta}


async def _run_hung_op(lines: list) -> tuple:
    target_id_seen = None
    timed_out = False

    async def _hung_op():
        nonlocal target_id_seen
        tab = await new_tab()
        target_id_seen = getattr(tab, '_target_id', None)
        try:
            # about:blank load is instant; then a never-resolving JS Promise simulates
            # the production TIMEOUT_NONCOOP scenario (execute_script waiting for CDP
            # Runtime.evaluate response that never comes). Browser process stays responsive
            # so close_target via browser connection completes in <100ms after cancel.
            await tab.go_to("about:blank", timeout=5)
            await tab.execute_script(
                "return new Promise(function() {})", await_promise=True
            )
        finally:
            await kill_tab(tab)

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(_hung_op(), timeout=WATCHDOG)
    except asyncio.TimeoutError:
        timed_out = True
    except Exception as e:
        lines.append(f"Unexpected exception: {type(e).__name__}: {e}")

    wall_ms = round((time.perf_counter() - t0) * 1000)
    return target_id_seen, timed_out, wall_ms


# Baseline: normal tab, no hang — kill_tab should still work correctly
async def _test_normal_tab_cleanup(lines: list) -> dict:
    lines.append("## Test 2 — normal tab (about:blank) with kill_tab in finally")
    lines.append("")

    renderers_before = _count_renderers()
    lines.append(f"Renderer count before: {renderers_before}")

    target_id_seen = None
    completed_ok = False

    async def _normal_op():
        nonlocal target_id_seen, completed_ok
        tab = await new_tab()
        target_id_seen = getattr(tab, '_target_id', None)
        try:
            await tab.go_to("about:blank", timeout=5)
            completed_ok = True
        finally:
            await kill_tab(tab)

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(_normal_op(), timeout=10.0)
    except asyncio.TimeoutError:
        lines.append("Unexpected TimeoutError on normal tab!")
    except Exception as e:
        lines.append(f"Unexpected exception: {type(e).__name__}: {e}")

    wall_ms = round((time.perf_counter() - t0) * 1000)

    tabs_open = _browser_mod._browser._tabs_opened if _browser_mod._browser else {}
    registry_clean = (target_id_seen not in tabs_open) if target_id_seen else True

    await asyncio.sleep(0.3)
    renderers_after = _count_renderers()
    renderers_delta = renderers_before - renderers_after

    passed = completed_ok and registry_clean and wall_ms < 8000

    lines.append(f"Completed without timeout: {completed_ok}")
    lines.append(f"Wall time: {wall_ms}ms")
    lines.append(f"Registry clean: {registry_clean}  (target_id={target_id_seen})")
    lines.append(f"Renderer count after: {renderers_after} (delta={renderers_delta:+d})")
    lines.append(f"**Result: {'PASS' if passed else 'FAIL'}**")
    lines.append("")

    return {'pass': passed, 'wall_ms': wall_ms, 'registry_clean': registry_clean, 'renderers_delta': renderers_delta}


# Count open CDP targets (tabs) via browser-level Target.getTargets — reliable on macOS headless
# where pgrep --type=renderer returns 0. Filters to type="page" only (excludes service workers etc.)
async def _count_cdp_targets() -> int:
    if not _browser_mod._browser:
        return 0
    targets = await _browser_mod._browser.get_targets()
    return sum(1 for t in targets if t.get('type') == 'page')


# End-to-end: N=5 hung tabs via asyncio.gather — mirrors production 5-engine pydoll fanout.
# All tabs hang on chrome://hang; watchdog fires on the gather; kill_tab in each finally.
# Primary metric: CDP target count (via browser connection) back to baseline after gather.
async def _test_batch_parallel_hung(lines: list) -> dict:
    lines.append(f"## Test 3 — parallel batch ({BATCH_N}x hung Promise) via asyncio.gather")
    lines.append("")
    lines.append(f"Mirrors production 5-engine pydoll fanout. Watchdog per task: {WATCHDOG}s")
    lines.append(f"Measurement: CDP Target.getTargets (type=page) via browser connection.")
    lines.append("")

    cdp_baseline = await _count_cdp_targets()
    lines.append(f"CDP page-targets baseline: {cdp_baseline}")

    collected_ids, all_timed_out, wall_ms = await _run_batch_hung(lines)

    await asyncio.sleep(0.3)
    cdp_after = await _count_cdp_targets()
    cdp_targets_delta = cdp_after - cdp_baseline

    tabs_open = _browser_mod._browser._tabs_opened if _browser_mod._browser else {}
    orphaned_ids = [tid for tid in collected_ids if tid and tid in tabs_open]
    registry_clean = len(orphaned_ids) == 0

    passed = all_timed_out and wall_ms < FAST_THRESHOLD_MS and registry_clean and cdp_targets_delta == 0

    lines.append(f"All {BATCH_N} tasks timed out (watchdog fired): {all_timed_out}")
    lines.append(f"Wall time: **{wall_ms}ms** (vs old up to {BATCH_N}×65s={BATCH_N*65000}ms sequential hang)")
    lines.append(f"CDP page-targets after: {cdp_after} (Δ={cdp_targets_delta:+d} vs baseline)")
    lines.append(f"Registry clean (no orphaned tab IDs): {registry_clean}  orphaned={orphaned_ids}")
    lines.append(f"**Result: {'PASS' if passed else 'FAIL'}**")
    lines.append("")

    return {
        'pass': passed,
        'wall_ms': wall_ms,
        'registry_clean': registry_clean,
        'cdp_targets_delta': cdp_targets_delta,
    }


async def _run_batch_hung(lines: list) -> tuple[list, bool, int]:
    collected_ids: list = []
    all_timed_out = True

    async def _one_hung_op(idx: int):
        nonlocal all_timed_out
        tab = await new_tab()
        tid = getattr(tab, '_target_id', None)
        collected_ids.append(tid)
        try:
            # Navigate first so the renderer is healthy (browser IPC stays responsive).
            # Then execute a never-resolving Promise with await_promise=True — renderer
            # waits indefinitely on the Promise; browser process stays fully responsive
            # so close_target via browser connection completes instantly after cancel.
            # (chrome://hang hangs Chrome's IPC too, causing close_target itself to stall.)
            await tab.go_to("about:blank", timeout=5)
            await tab.execute_script(
                "return new Promise(function() {})", await_promise=True
            )
        finally:
            await kill_tab(tab)

    async def _watchdog_wrapped(idx: int):
        nonlocal all_timed_out
        try:
            await asyncio.wait_for(_one_hung_op(idx), timeout=WATCHDOG)
            all_timed_out = False
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            lines.append(f"  Task {idx} unexpected: {type(e).__name__}: {e}")
            all_timed_out = False

    t0 = time.perf_counter()
    await asyncio.gather(*[_watchdog_wrapped(i) for i in range(BATCH_N)])
    wall_ms = round((time.perf_counter() - t0) * 1000)
    return collected_ids, all_timed_out, wall_ms


if __name__ == "__main__":
    asyncio.run(pydoll_teardown_verify_workflow())
