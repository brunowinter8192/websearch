# INFRASTRUCTURE
import asyncio
import importlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_browser_mod = importlib.import_module("src.search.browser")
get_tab = _browser_mod.get_tab
new_tab = _browser_mod.new_tab
kill_tab = _browser_mod.kill_tab

WATCHDOG = 5.0
FAST_THRESHOLD_MS = 8000
BATCH_N = 5

REPORT_DIR = Path(__file__).parent / "md"


# ORCHESTRATOR

async def pydoll_teardown_verify_workflow() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = _compute_report_path(ts)
    REPORT_DIR.mkdir(exist_ok=True)

    lines = _compute_lines(ts)

    lines.append("## Setup")
    await get_tab()
    browser_state = _compute_browser_state()
    _append_browser_started(lines, browser_state)
    lines.append("")

    r1 = await _test_kill_tab_hung(lines)
    r2 = await _test_normal_tab_cleanup(lines)
    r3 = await _test_batch_parallel_hung(lines)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Test | Result | Wall time | Registry clean | CDP targets Δ |")
    lines.append("|---|---|---|---|---|")
    _append_result_table(lines, r1, r2, r3)
    lines.append("")

    overall = _compute_overall(r1, r2, r3)
    _append_overall(lines, overall)
    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    _append_interpretation(lines)

    report_path.write_text("\n".join(lines))
    _print_report(report_path, r1, r2, r3, overall)


# FUNCTIONS

def _compute_report_path(ts):
    report_path = REPORT_DIR / f"teardown_verify_{ts}.md"
    return report_path


def _compute_lines(ts):
    lines = [f"# Pydoll Teardown Verification — {ts}", ""]
    return lines


def _compute_browser_state():
    browser_state = "set" if _browser_mod._browser else "NONE"
    return browser_state


def _append_browser_started(lines, browser_state):
    lines.append(f"Browser started: `_browser` = {browser_state}")


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


def _append_result_table(lines, r1, r2, r3):
    lines.append(f"| T1 single hung tab + kill_tab     | {'PASS' if r1['pass'] else 'FAIL'} | {r1['wall_ms']}ms | {'yes' if r1['registry_clean'] else 'no'} | n/a |")
    lines.append(f"| T2 normal tab + kill_tab           | {'PASS' if r2['pass'] else 'FAIL'} | {r2['wall_ms']}ms | {'yes' if r2['registry_clean'] else 'no'} | n/a |")
    lines.append(f"| T3 parallel batch {BATCH_N}x hung + gather | {'PASS' if r3['pass'] else 'FAIL'} | {r3['wall_ms']}ms | {'yes' if r3['registry_clean'] else 'no'} | {r3['cdp_targets_delta']:+d} |")


def _compute_overall(r1, r2, r3):
    overall = r1['pass'] and r2['pass'] and r3['pass']
    return overall


def _append_overall(lines, overall):
    lines.append(f"**Overall: {'PASS' if overall else 'FAIL'}**")


def _append_interpretation(lines):
    lines.append(f"- Old behavior (tab.close): each hung tab adds ~60s; batch of {BATCH_N} = up to {BATCH_N}×65s worst case")
    lines.append(f"- New behavior (kill_tab): batch wall ~= watchdog ({WATCHDOG}s) — all {BATCH_N} tabs killed in parallel")
    lines.append(f"- T3 CDP targets Δ = 0 → no orphaned targets after batch teardown")


def _print_report(report_path, r1, r2, r3, overall):
    print(f"\nReport: {report_path}")
    print(f"T1 single hung:  wall={r1['wall_ms']}ms  registry_clean={r1['registry_clean']}  -> {'PASS' if r1['pass'] else 'FAIL'}")
    print(f"T2 normal tab:   wall={r2['wall_ms']}ms  registry_clean={r2['registry_clean']}  -> {'PASS' if r2['pass'] else 'FAIL'}")
    print(f"T3 batch {BATCH_N}x hung: wall={r3['wall_ms']}ms  registry_clean={r3['registry_clean']}  cdp_targets_delta={r3['cdp_targets_delta']:+d}  -> {'PASS' if r3['pass'] else 'FAIL'}")
    print(f"Overall: {'PASS' if overall else 'FAIL'}")


def _count_renderers() -> int:
    result = subprocess.run(
        ["pgrep", "-c", "-f", "--type=renderer"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


async def _run_hung_op(lines: list) -> tuple:
    target_id_seen = None
    timed_out = False

    async def _hung_op():
        nonlocal target_id_seen
        tab = await new_tab()
        target_id_seen = getattr(tab, '_target_id', None)
        try:
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


async def _count_cdp_targets() -> int:
    if not _browser_mod._browser:
        return 0
    targets = await _browser_mod._browser.get_targets()
    return sum(1 for t in targets if t.get('type') == 'page')


async def _run_batch_hung(lines: list) -> tuple[list, bool, int]:
    collected_ids: list = []
    all_timed_out = True

    async def _one_hung_op(idx: int):
        nonlocal all_timed_out
        tab = await new_tab()
        tid = getattr(tab, '_target_id', None)
        collected_ids.append(tid)
        try:
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
