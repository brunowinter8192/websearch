# INFRASTRUCTURE
from pathlib import Path


# FUNCTIONS
def _render_header(ts: str, test_url: str, baseline_status: int | None) -> list:
    lines = ["# CoinDesk IP Warmth Probe Report"]
    lines.append(f"\n**Run:** {ts}\n")
    lines.append(f"**Test URL (fixed for all calls):** `{test_url}`\n")
    lines.append(f"**Baseline (Chrome still open):** `{baseline_status}`\n")
    return lines


def _render_ladder_section(intervals: list, ladder_results: list) -> list:
    lines = ["## Phase W — Warmth Timing Ladder\n"]
    lines.append("Same URL replayed at cumulative T seconds after Chrome closes.\n")
    lines.append("| T (s after close) | Status | Call elapsed | Notes |")
    lines.append("|-------------------|--------|--------------|-------|")
    for r in ladder_results:
        snippet = r.get("body_snippet") or ""
        notes = f"`{snippet[:60]}`" if snippet else "—"
        lines.append(
            f"| {r['t_seconds']} | **{r['status']}** |"
            f" {r.get('call_elapsed', r.get('error', '?'))}s | {notes} |"
        )

    first_403 = next((r for r in ladder_results if r["status"] != 200), None)
    last_200_idx = max(
        (i for i, r in enumerate(ladder_results) if r["status"] == 200), default=-1
    )

    if first_403 is None:
        lines.append(f"\n✅ **No 403 in {intervals[-1]}s** — warmth lasts at least {intervals[-1]}s.\n")
    else:
        last_200_t = ladder_results[last_200_idx]["t_seconds"] if last_200_idx >= 0 else "?"
        lines.append(
            f"\n**Warmth window:** last 200 at T={last_200_t}s,"
            f" first non-200 at T={first_403['t_seconds']}s.\n"
        )
    return lines


def _render_feedpage_section(target_url: str, feedpage_result: dict | None) -> list:
    if feedpage_result is None:
        return []
    lines = ["## Phase C-1 — Feedpage Rewarm Test\n"]
    lines.append(
        "Plain `httpx.get` of the feed HTML page (no browser) after warmth expired:\n"
    )
    lines.append(
        f"- `httpx.get(\"{target_url}\")` → HTTP {feedpage_result['feedpage_status']}"
        f" ({feedpage_result['feedpage_bytes']} bytes)"
    )
    api_after = feedpage_result["api_after_feedpage"]
    lines.append(f"- API call immediately after → **{api_after}**\n")
    if api_after == 200:
        lines.append("✅ **httpx feedpage GET IS sufficient to re-warm the IP.**\n")
    else:
        snip = feedpage_result.get("api_after_feedpage_snippet") or ""
        lines.append(f"❌ **httpx feedpage GET does NOT re-warm** — browser required.")
        if snip:
            lines.append(f"\nAPI body snippet: `{snip[:100]}`\n")
    return lines


def _render_subprocess_section(subprocess_result: dict | None) -> list:
    if subprocess_result is None:
        return []
    lines = ["## Phase C-2 — Subprocess Cold Test\n"]
    lines.append(
        "Fresh `python` subprocess loads `state.json` (URL + headers),"
        " calls the API with NO prior coindesk connection in that process.\n"
    )
    sub_status = subprocess_result.get("status", "?")
    lines.append(f"- Subprocess → **{sub_status}**")
    if subprocess_result.get("stderr"):
        lines.append(f"- stderr: `{subprocess_result['stderr'][:200]}`\n")
    if sub_status == "200":
        lines.append("\nSubprocess → 200: warmth is **IP-level** (not process-level).\n")
    elif sub_status and sub_status.startswith(("4", "5")):
        lines.append(
            f"\nSubprocess → {sub_status}: consistent with IP warmth expired"
            f" (both parent + subprocess cold — IP-level check).\n"
        )
    else:
        lines.append(f"\nSubprocess result ambiguous: `{subprocess_result}`\n")
    return lines


# Write warmth probe report (MD)
def write_warmth_report(
    path: Path,
    ts: str,
    target_url: str,
    test_url: str,
    baseline_status: int | None,
    intervals: list,
    ladder_results: list,
    feedpage_result: dict | None,
    subprocess_result: dict | None,
) -> None:
    lines = []
    lines += _render_header(ts, test_url, baseline_status)
    lines += _render_ladder_section(intervals, ladder_results)
    lines += _render_feedpage_section(target_url, feedpage_result)
    lines += _render_subprocess_section(subprocess_result)
    path.write_text("\n".join(lines), encoding="utf-8")
