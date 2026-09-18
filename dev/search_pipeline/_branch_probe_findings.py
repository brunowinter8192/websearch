# INFRASTRUCTURE
import statistics
from datetime import datetime
from pathlib import Path

from _branch_probe_canary import _canary_stats
from _branch_probe_report import _overall_verdict


# FUNCTIONS

def _write_findings(
    records: list[dict],
    report_path: Path,
    cascade_ok: bool,
    zero_n: int,
    findings_dir: Path,
    backoff_immune: frozenset[str],
) -> Path:
    path = findings_dir / "03_branch_probe.md"
    verdict = _overall_verdict(records)
    cstats = _canary_stats(records)
    report_rel = report_path.relative_to(Path(__file__).parent.parent.parent)
    ts_str = datetime.now().strftime("%Y-%m-%d")

    zc_records = [r for r in records if r["category"] == "zero_cascade"]
    avg_ba, avg_tc, avg_ni, immune_ba_any = _findings_averages(zc_records, backoff_immune)
    s_zc = cstats["zero_cascade"]
    verdict_text = _verdict_text(verdict, avg_ba, avg_tc, avg_ni, immune_ba_any)

    lines = _findings_header(ts_str, verdict, cascade_ok, zero_n, records, report_rel)
    lines += _findings_narrative()
    lines += _findings_key_numbers(zero_n, avg_ba, avg_tc, avg_ni, s_zc)
    lines += _findings_verdict_section(verdict_text)
    if immune_ba_any and verdict in ("backoff", "mixed"):
        lines += _findings_side_finding()
    lines += _findings_next_steps(verdict)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _findings_averages(zc_records: list[dict], backoff_immune: frozenset[str]):
    avg_ba = avg_tc = avg_ni = "—"
    immune_ba_any = False
    if zc_records:
        ba_per, tc_per, ni_per = [], [], []
        for r in zc_records:
            rs = [d for d in r["eng_detail"].values() if d["status"] == "RATE_SKIP"]
            n = len(rs) or 1
            ba_per.append(sum(1 for d in rs if d["backoff_attempt"]) / n)
            tc_per.append(sum(1 for d in rs if d["tokencap_attempt"]) / n)
            ni_per.append(
                sum(1 for d in rs if not d["backoff_attempt"] and not d["tokencap_attempt"]) / n
            )
        mn = statistics.mean
        avg_ba = round(mn(ba_per), 2)
        avg_tc = round(mn(tc_per), 2)
        avg_ni = round(mn(ni_per), 2)
        immune_ba_any = any(
            d["backoff_attempt"]
            for r in zc_records
            for eng, d in r["eng_detail"].items()
            if eng in backoff_immune and d["status"] == "RATE_SKIP"
        )
    return avg_ba, avg_tc, avg_ni, immune_ba_any


def _verdict_text(verdict: str, avg_ba, avg_tc, avg_ni, immune_ba_any: bool) -> str:
    return {
        "tokencap": (
            "**tokencap-path wins.** ALL RATE_SKIP engines — including backoff-immune engines "
            "(crossref, openalex, stack_exchange, open_library) — fired the "
            "`len(tokens) >= max_requests` branch. No engine fired the backoff branch. "
            "The uniform 4 req/60s cap saturates within the batch-query window: 4 successful "
            "queries in <60s fills each engine's token bucket; the 5th acquire() sleeps waiting "
            "for the oldest token to age out (planned wait ≈ 60s − age_of_oldest_token, typically "
            "40–55s). asyncio.wait_for cancels at 5s → CancelledError → RATE_SKIP. "
            "Phase 2 multi-engine backoff-cascade narrative is INCORRECT for this scenario."
        ),
        "backoff": (
            "**backoff-path wins.** ALL RATE_SKIP engines fired the `if now < _backoff_until:` "
            f"branch. {'Includes backoff-IMMUNE engines (crossref, openalex, stack_exchange, open_library) → an unknown code path calls .backoff() on these limiters. Grep src/ for .backoff() call sites.' if immune_ba_any else 'Only backoff-capable engines fired — consistent with Phase 2 narrative.'} "
            "Phase 2 multi-engine backoff-cascade narrative CONFIRMED."
        ),
        "mixed": (
            f"**mixed.** Both branches fired across engines within zero_cascade queries. "
            f"avg per query: backoff={avg_ba} engines, tokencap={avg_tc} engines, neither={avg_ni}. "
            f"{'Backoff-immune engines appeared in backoff group → unknown .backoff() call site exists. ' if immune_ba_any else ''}"
            "Multi-cause cascade: some engines genuinely backed off, others at token-cap saturation."
        ),
        "neither": (
            "**neither.** RATE_SKIP engines got CancelledError but no sleep branch was entered. "
            "CancelledError arrives before reaching asyncio.sleep — unexpected given Phase 2 "
            "lock_granted=Y. Investigate lock acquisition timing."
        ),
        "no_cascade": (
            "**no_cascade.** Zero cascade did not reproduce — data INVALID."
        ),
    }.get(verdict, f"**{verdict}** — see per-query detail in report.")


def _findings_header(
    ts_str: str,
    verdict: str,
    cascade_ok: bool,
    zero_n: int,
    records: list[dict],
    report_rel: Path,
) -> list[str]:
    return [
        "# Bee CDP Starvation — Phase 3 Branch Probe",
        "",
        f"**Date:** {ts_str}  ",
        f"**Verdict:** {verdict}  ",
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
        "Phase 2 confirmed A-sleep: all 9 engines enter `acquire()`, get lock, sleep, get",
        "cancelled at ~5001ms. Phase 2 inferred backoff-cascade (Google CAPTCHA sets",
        "`backoff_until`, non-Google engines follow suit via their own 429/bot-detect calls).",
        "That inference was NOT probe-verified — Phase 2 instrumentation was a wrapper around",
        "the original `acquire()` and did not distinguish which of the two `asyncio.sleep`",
        "branches fired.",
        "",
        "Two branches in `acquire()` (rate_limiter.py):",
        "- **backoff branch** (line 36): `if now < self._backoff_until:` — fires only if engine",
        "  called `.backoff()`. 6 engines have `.backoff()` in source; 4 do NOT.",
        "- **tokencap branch** (line 47): `if len(self._tokens) >= self._max_requests:` — fires",
        "  when 4 tokens in the 60s window. After 4 successful queries in <60s, ANY engine hits this.",
        "",
        "Structural discriminator: crossref, openalex, stack_exchange, open_library have NO",
        "`.backoff()` call in engine source. If they show `backoff_sleep_attempt=Y`, an unknown",
        "code path calls `.backoff()` on them — that would be a new finding.",
        "",
        "## Instrumentation",
        "",
        "- **Layer 1** — `_snapshot_limiters()`: per-engine `{backoff_remaining_s, len_tokens}`",
        "  captured immediately before each `search_web_workflow` call.",
        "- **Layer 2** — `_replacement_acquire()`: full replacement of `RateLimiter.acquire()`",
        "  (NOT a wrapper around original). Byte-identical body + `backoff_sleep_attempt` /",
        "  `tokencap_sleep_attempt` events emitted before each `await asyncio.sleep`.",
        "  Event tuple: `(engine, event, ts_mono, wait_s)`.",
        "- **Layer 3** — canary task (Pattern B, identical to Phase 1+2): scheduling latency.",
        "",
        "No `_WatchedLock` / `__init__` patch (Phase 2 proved lock_granted=Y; lock events unneeded).",
        "",
    ]


def _findings_key_numbers(zero_n: int, avg_ba, avg_tc, avg_ni, s_zc: dict) -> list[str]:
    return [
        "## Key Numbers",
        "",
        "| Category | n_q | avg_backoff_eng/q | avg_tokencap_eng/q | avg_neither_eng/q | canary_p99_ms |",
        "|----------|-----|------------------:|-------------------:|------------------:|:--------------|",
        f"| zero_cascade | {zero_n} | {avg_ba} | {avg_tc} | {avg_ni} | {s_zc['p99']} |",
        "",
    ]


def _findings_verdict_section(verdict_text: str) -> list[str]:
    return [
        "## Verdict",
        "",
        verdict_text,
        "",
    ]


def _findings_side_finding() -> list[str]:
    return [
        "## Key Side Finding: Backoff-Immune Engine in Backoff Branch",
        "",
        "crossref / openalex / stack_exchange / open_library showed `backoff_sleep_attempt=Y`",
        "despite having no `.backoff()` call in their engine source. Possible causes:",
        "(a) cross-cutting code in `search_web.py` orchestration calls `.backoff()` on all",
        "    limiters on CAPTCHA/error detection, OR",
        "(b) `get_limiter()` returning a shared instance due to aliased key.",
        "Next step: `grep -rn '\\.backoff()' src/` to locate all call sites.",
        "",
    ]


def _findings_next_steps(verdict: str) -> list[str]:
    lines = [
        "## Next Steps",
        "",
        "Pending (bead `searxng-bee`):",
    ]
    if verdict == "tokencap":
        lines += [
            "- Fix: raise per-engine `max_requests` from 4 to align with `MAX_REQUESTS=10` default,",
            "  OR add inter-query minimum delay in `search_batch_workflow` (≥15s keeps bucket from",
            "  filling in a 60s window with typical 5-10s query durations),",
            "  OR detect token saturation pre-acquire and skip engine gracefully (no 5s wait).",
            "- Phase 2 backoff-cascade narrative was based on inference, not measurement. The",
            "  backoff() calls in engine source are real but NOT the dominant cascade mechanism here.",
        ]
    elif verdict == "backoff":
        lines += [
            "- Identify which non-Google engines have `backoff_until` set and what triggered it.",
            "- Instrument `.backoff()` call sites (6 engines) to log which backend returned 429/403.",
            "- Consider reducing BACKOFF_BASE from 30s or adding per-engine tuning.",
        ]
    elif verdict == "mixed":
        lines += [
            "- For tokencap-affected engines: raise max_requests or add inter-query delay.",
            "- For backoff-affected engines: instrument .backoff() call sites.",
            "- Immune engines in backoff group → grep src/ for unexpected .backoff() calls.",
        ]
    lines.append("")
    return lines
