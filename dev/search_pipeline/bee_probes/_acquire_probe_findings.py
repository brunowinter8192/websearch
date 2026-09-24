# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path

from _acquire_probe_canary import _canary_stats
from _acquire_probe_analysis import _agg_ratios
from _acquire_probe_report import _overall_disc


# FUNCTIONS

def _write_findings(
    records: list[dict],
    report_path: Path,
    cascade_ok: bool,
    zero_n: int,
    findings_dir: Path,
) -> Path:
    path = findings_dir / "02_acquire_probe.md"
    od = _overall_disc(records)
    cstats = _canary_stats(records)
    report_rel = report_path.relative_to(Path(__file__).parent.parent.parent.parent)

    zc_records = [r for r in records if r["category"] == "zero_cascade"]
    if zc_records:
        ent, lg, ok, err, dp99 = _agg_ratios(zc_records)
    else:
        ent = lg = ok = err = dp99 = "—"

    normal_n = sum(1 for r in records if r["category"] == "normal")
    empty_n = sum(1 for r in records if r["category"] == "empty")
    disc_text = _disc_text(od)

    lines = _findings_header(od, cascade_ok, zero_n, records, report_rel)
    lines += _findings_narrative()
    lines += _findings_key_numbers(normal_n, empty_n, zero_n, ent, lg, ok, err, dp99, cstats)
    lines += _findings_verdict_section(disc_text)
    lines += _findings_next_steps(od)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _disc_text(od: str) -> str:
    return {
        "B": (
            "**B wins.** `acquire()` Tasks were never started — `asyncio.wait_for` timeout fired "
            "before the inner Task got a scheduler turn. Event loop IS free (canary confirms), so "
            "the scheduling gap is specific to how `asyncio.wait_for` + `asyncio.gather` interact "
            "in Python 3.14 with a long-sleeping peer Task (Google's backoff sleep)."
        ),
        "A-lock": (
            "**A-lock wins.** `acquire()` Tasks entered (`enter` recorded) but never received the "
            "lock (`lock_granted` absent). Consistent with Python 3.14 `asyncio.Lock.__aexit__` "
            "failing to release the lock under `CancelledError` propagated via `asyncio.wait_for` "
            "timeout. Each cancelled acquire() leaves `self._lock` held. The next query's "
            "`acquire()` blocks on `async with self._lock:` indefinitely — times out again — "
            "perpetuating the cascade across all subsequent queries."
        ),
        "A-sleep": (
            "**A-sleep wins.** `acquire()` Tasks entered AND received the lock (`lock_granted` "
            "present) but timed out inside `asyncio.sleep(backoff_s)`. Expected for Google "
            "(backoff set by CAPTCHA). If non-Google engines also show this, their `backoff_until` "
            "was set unexpectedly — investigate `backoff()` call sites."
        ),
        "C": (
            "**C wins.** All `acquire()` calls completed normally (exit_ok). RATE_SKIP is assigned "
            "outside `acquire()` — investigate `_engine_with_timing` return path."
        ),
        "no_cascade": (
            "**no_cascade.** Zero cascade did not reproduce. Instrumentation may be interfering "
            "with timing. Data INVALID."
        ),
    }.get(od, f"**{od}** — mixed result, see per-query detail table in report.")


def _findings_header(
    od: str,
    cascade_ok: bool,
    zero_n: int,
    records: list[dict],
    report_rel: Path,
) -> list[str]:
    return [
        "# Bee CDP Starvation — Phase 2 Acquire Probe",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}  ",
        f"**Verdict:** {od}  ",
        f"**Cascade reproduced:** {cascade_ok} ({zero_n}/{len(records)} zero_cascade)  ",
        f"**Report:** `{report_rel}`  ",
        "",
        "---",
        "",
    ]


def _findings_narrative() -> list[str]:
    return [
        "## Hypothesis",
        "",
        "Phase 1 REFUTED CDP event-loop starvation (scheduling latency p99=1.4ms; 0 CDP events",
        "during zero_cascade). Chrome is silent. Event loop is free. Yet all 9+ engines show",
        "RATE_SKIP with rate_wait_ms≈5000ms (=RATE_WAIT_TIMEOUT). Three candidates:",
        "",
        "- **B:** `asyncio.wait_for` timeout fires before inner `acquire()` Task is scheduled.",
        "- **A-lock:** Task runs, enters `async with self._lock:`, blocks (stale lock from prior",
        "  cancelled acquire() where Python 3.14 `Lock.__aexit__` did not release).",
        "- **A-sleep:** Task runs, gets lock, blocks on `asyncio.sleep(backoff_s)` inside.",
        "  Plausible only for Google (backoff set by CAPTCHA). Non-Google have no backoff.",
        "- **C:** acquire() completes fine — bug is downstream of acquire().",
        "",
        "## Instrumentation",
        "",
        "Two monkey-patches on `RateLimiter` class (applied before search_web import):",
        "",
        "- **`acquire()` wrapper** — records `enter`, `exit_ok`, `exit_err:<class>` per engine.",
        "- **`__init__` wrapper** → `_WatchedLock` replaces `self._lock` — records",
        "  `lock_attempt`, `lock_granted`, `lock_released`/`lock_stuck` via Lock wrappers.",
        "  `lock_stuck` = lock.locked() still True after __aexit__ returns (non-release signal).",
        "",
        "Pattern B canary re-runs for triangulation (same as Phase 1).",
        "",
    ]


def _findings_key_numbers(
    normal_n: int,
    empty_n: int,
    zero_n: int,
    ent, lg, ok, err, dp99,
    cstats: dict[str, dict],
) -> list[str]:
    s_norm = cstats["normal"]
    s_zc = cstats["zero_cascade"]
    return [
        "## Key Numbers",
        "",
        "| Category | n_q | avg_ent | avg_lg | avg_ok | avg_err | dur_p99_ms | canary_p99_ms |",
        "|----------|-----|---------|--------|--------|---------|------------|---------------|",
        f"| normal | {normal_n} | — | — | — | — | — | {s_norm['p99']} |",
        f"| empty | {empty_n} | — | — | — | — | — | — |",
        f"| zero_cascade | {zero_n} | {ent} | {lg} | {ok} | {err} | {dp99} | {s_zc['p99']} |",
        "",
    ]


def _findings_verdict_section(disc_text: str) -> list[str]:
    return [
        "## Verdict",
        "",
        disc_text,
        "",
    ]


def _findings_next_steps(od: str) -> list[str]:
    lines = [
        "## Next Steps",
        "",
        "Pending (bead `searxng-bee`):",
    ]
    if od == "A-lock":
        lines += [
            "- Write minimal Python 3.14 repro: `asyncio.wait_for(coro_that_holds_lock, 0.001)` —",
            "  check if `lock.locked()` is True after timeout. If yes: confirmed Python 3.14 regression.",
            "- Fix option 1: remove `asyncio.Lock` from `RateLimiter.acquire()`. Concurrent",
            "  calls per engine are structurally safe (gather fanout calls each engine once per query).",
            "- Fix option 2: in `search_batch_workflow`, on CAPTCHA detection, reset all engine",
            "  limiters' `_lock = asyncio.Lock()` before proceeding to next query.",
        ]
    elif od == "B":
        lines += [
            "- Minimal repro: 9 concurrent `asyncio.wait_for(immediate_coro, 5.0)` with one",
            "  peer Task doing `asyncio.sleep(60)` — confirm inner Tasks complete before timeout.",
            "- Check Python 3.14 `asyncio.wait_for` source for Task scheduling deferral.",
        ]
    elif od == "A-sleep":
        lines += [
            "- Identify which non-Google engines have `backoff_until` set and why.",
            "- Check `backoff()` call sites for unintended cross-engine propagation.",
        ]
    elif od == "C":
        lines += ["- Investigate `_engine_with_timing` post-acquire status assignment."]
    lines.append("")
    return lines
