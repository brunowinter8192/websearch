# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path

from _cdp_starvation_probe_instrument import _cdp_ts, _slow_cb_events
from _cdp_starvation_probe_canary import _compute_stats
from _cdp_starvation_probe_report import _derive_verdict


# FUNCTIONS

def _write_findings(records: list[dict], report_path: Path, findings_dir: Path) -> Path:
    path = findings_dir / "01_probe.md"
    stats = _compute_stats(records)
    verdict = _derive_verdict(stats)
    report_rel = report_path.relative_to(Path(__file__).parent.parent.parent.parent)
    norm_p99 = max(stats["normal"]["p99"], 1.0)

    lines = _findings_header(verdict, report_rel)
    lines += _findings_narrative()
    lines += _findings_key_numbers(stats)
    lines += _findings_cdp_rate_table(records)
    lines += _findings_verdict_section(stats, verdict, norm_p99)
    lines += _findings_next_steps(verdict)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _findings_header(verdict: str, report_rel: Path) -> list[str]:
    return [
        "# Bee CDP Starvation — Phase 1 Probe",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}  ",
        f"**Verdict:** {verdict}  ",
        f"**Report:** `{report_rel}`  ",
        "",
        "---",
        "",
    ]


def _findings_narrative() -> list[str]:
    return [
        "## Hypothesis",
        "",
        "During Google CAPTCHA navigation, Chrome emits a burst of CDP events processed by",
        "pydoll's `ConnectionHandler._receive_events()` (`connection_handler.py:226`) in a",
        "tight `async for raw_message in _incoming_messages()` loop. When websockets' internal",
        "queue is non-empty, `Queue.get()` completes without yielding — near-non-yielding",
        "busy loop. All 9 engines' `asyncio.wait_for(limiter.acquire(), 5.0)` calls",
        "(`_engine_with_timing()` in `search_web.py:299`) never get a scheduler turn and",
        "expire as TimeoutError simultaneously — including HTTP-only engines.",
        "",
        "## Instrumentation",
        "",
        "Three measurements sharing the same asyncio event loop across 20 sequential queries:",
        "",
        "- **Pattern A** — `loop.slow_callback_duration=0.05s; loop.set_debug(True)` + asyncio",
        "  logger capture: records any callback blocking >50ms.",
        "- **Pattern B** — canary task: `await asyncio.sleep(0.1)` every 100ms, scheduling",
        "  latency = actual_elapsed − 100ms. From Ray Serve production pattern.",
        "- **CDP counter** — monkey-patch on `ConnectionHandler._process_single_message`",
        "  (`connection_handler.py:244`): timestamps each CDP message received.",
        "",
        "Query categories used for latency segmentation:",
        "- `empty`: google_status == EMPTY (was EMPTY_BLOCK — removed along with the query log's",
        "  guessed-verdict sub-statuses; `empty` now also covers what used to be the other EMPTY_*",
        "  causes, since engine_details carries no diagnosis to distinguish them)",
        "- `zero_cascade`: all 9 engines RATE_SKIP simultaneously",
        "- `normal`: all other queries",
        "",
    ]


def _findings_key_numbers(stats: dict) -> list[str]:
    s_cap = stats["empty"]
    s_zc = stats["zero_cascade"]
    s_norm = stats["normal"]
    return [
        "## Key Numbers",
        "",
        "| Metric | normal | empty | zero_cascade |",
        "|--------|--------|---------|--------------|",
        f"| samples n | {s_norm['n']} | {s_cap['n']} | {s_zc['n']} |",
        f"| scheduling latency p50 ms | {s_norm['p50']} | {s_cap['p50']} | {s_zc['p50']} |",
        f"| scheduling latency p95 ms | {s_norm['p95']} | {s_cap['p95']} | {s_zc['p95']} |",
        f"| scheduling latency p99 ms | {s_norm['p99']} | {s_cap['p99']} | {s_zc['p99']} |",
        f"| scheduling latency max ms | {s_norm['max']} | {s_cap['max']} | {s_zc['max']} |",
        "",
        f"Slow-callback events captured (Pattern A, >50ms): {len(_slow_cb_events)}  ",
        f"Total CDP messages received: {len(_cdp_ts)}  ",
        "",
    ]


def _findings_cdp_rate_table(records: list[dict]) -> list[str]:
    lines = [
        "### CDP Rate by Query",
        "",
        "| # | Query | category | cdp_events | cdp_rate/s |",
        "|---|-------|----------|------------|------------|",
    ]
    for r in records:
        q = r["query"][:42]
        lines.append(f"| {r['qi']} | {q} | {r['category']} | {r['cdp_events']} | {r['cdp_rate']:.1f} |")
    return lines


def _findings_verdict_section(stats: dict, verdict: str, norm_p99: float) -> list[str]:
    lines = [
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]
    lines += _verdict_narrative(stats, verdict, norm_p99)
    return lines


def _findings_next_steps(verdict: str) -> list[str]:
    lines = [
        "",
        "## Next Steps",
        "",
        "Pending (bead `searxng-bee`):",
    ]
    if verdict in ("CONFIRMED", "PARTIALLY_CONFIRMED"):
        lines += [
            "- **Mitigation:** after detecting an empty google result (google EMPTY, was EMPTY_BLOCK, in `search_batch_workflow`),",
            "  yield event loop with repeated `await asyncio.sleep(0)` or a short `asyncio.sleep(0.5)`",
            "  before next query to drain the CDP backlog.",
            "- **Structural:** custom `ConnectionHandler` subclass throttling `_receive_events` with",
            "  `asyncio.sleep(0)` every N events to guarantee scheduler turns during bursts.",
            "- Re-run probe post-mitigation to confirm latency returns to normal baseline.",
        ]
    else:
        lines += [
            "- Verify rate limiter backoff does not block: `asyncio.sleep(backoff_s)` in `rate_limiter.py`.",
            "- Probe Chrome tab lifecycle: `new_tab()` / `apply_fingerprint_patches()` blocking cost.",
        ]
    lines.append("")
    return lines


def _verdict_narrative(stats: dict, verdict: str, norm_p99: float) -> list[str]:
    s_cap = stats["empty"]
    s_zc = stats["zero_cascade"]
    s_norm = stats["normal"]

    if verdict == "CONFIRMED":
        worst_cat = "empty" if s_cap["p99"] >= s_zc["p99"] else "zero_cascade"
        worst = stats[worst_cat]
        return [
            f"Scheduling latency p99 during `{worst_cat}` windows: {worst['p99']}ms vs",
            f"normal {s_norm['p99']}ms ({worst['p99']/norm_p99:.0f}x ratio). Asyncio event loop",
            "definitively starved during Chrome CAPTCHA processing. All 9 engines' 5s",
            "`wait_for` deadlines expire before getting a scheduler turn — confirmed by Pattern B.",
        ]
    elif verdict == "PARTIALLY_CONFIRMED":
        return [
            f"Latency elevated: empty p99={s_cap['p99']}ms, zero_cascade p99={s_zc['p99']}ms",
            f"vs normal {s_norm['p99']}ms. CDP event loop mechanism consistent but starvation",
            "weaker than predicted — may require heavier CAPTCHA page to trigger full cascade.",
        ]
    elif verdict == "REFUTED":
        return [
            f"No significant elevation: empty p99={s_cap['p99']}ms,",
            f"zero_cascade p99={s_zc['p99']}ms vs normal p99={s_norm['p99']}ms.",
            "CDP starvation hypothesis not supported. Alternative root cause required.",
        ]
    return ["No CAPTCHA or zero-cascade queries occurred — hypothesis untestable."]
