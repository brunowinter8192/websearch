# INFRASTRUCTURE
import json
from pathlib import Path

from _04_capture import CLICKS_TO_TRIGGER, TIMELINE_API_PATH


# FUNCTIONS
def _render_captured_request(api_url: str) -> list:
    lines = ["## Captured Request\n"]
    lines.append(f"**URL:** `{api_url}`\n")
    return lines


def _render_headers_section(raw_headers: dict, replay_headers: dict) -> list:
    lines = ["## Request Headers (replay set)\n"]
    lines.append(f"Raw headers from HAR: **{len(raw_headers)}** | After pseudo-header strip: **{len(replay_headers)}**\n")
    lines.append("| Header | Value |")
    lines.append("|--------|-------|")
    for k in sorted(replay_headers.keys()):
        v = replay_headers[k]
        v_disp = (v[:100] + "…") if len(v) > 100 else v
        lines.append(f"| `{k}` | `{v_disp}` |")

    stripped = sorted(set(raw_headers.keys()) - set(replay_headers.keys()))
    if stripped:
        lines.append(f"\n**Stripped:** `{', '.join(stripped)}`\n")
    return lines


def _render_replay_results(replay_results: dict) -> list:
    lines = ["\n## Replay Results\n"]
    lines.append("| Client | Status | Error |")
    lines.append("|--------|--------|-------|")
    for client, (status, err) in replay_results.items():
        err_disp = (str(err)[:80] + "…") if err and len(str(err)) > 80 else (str(err) if err else "—")
        lines.append(f"| {client} | **{status}** | {err_disp} |")
    return lines


def _render_json_sample(first_json_sample: dict | None) -> list:
    if not first_json_sample:
        return []
    lines = ["\n## Response JSON Structure (first 200 response)\n"]
    lines.append("```json")
    lines.append(json.dumps(first_json_sample, indent=2, ensure_ascii=False))
    lines.append("```\n")
    return lines


def _render_cursor_summary(summary: dict) -> list:
    lines = ["### Summary\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Successful calls | {summary['total_calls']} |")
    lines.append(f"| Total articles fetched | {summary['total_articles']} |")
    lines.append(f"| Oldest date reached | {summary['oldest_date']} |")
    lines.append(f"| Avg elapsed per call | {summary['avg_elapsed']}s |")
    lines.append(f"| Non-200 responses | {summary['non_200']} |\n")
    return lines


# 403 diagnostics block (if present)
def _render_403_diagnostics(diag: dict) -> list:
    lines = ["\n### 403 Diagnostics\n"]
    lines.append(f"**Failing URL:** `{diag.get('failing_url', '?')}`\n")
    lines.append(f"**Status:** httpx={diag.get('status_httpx')} curl_cffi={diag.get('status_curl')}\n")
    rec = diag.get("recoverability", {})
    lines.append("**Recoverability:**\n")
    lines.append(f"- Retry at +10s → `{rec.get('retry_at_10s')}`")
    lines.append(f"- Retry at +40s → `{rec.get('retry_at_40s')}`\n")
    lines.append("**Cursor-source article (last of previous call):**\n")
    lines.append("```json")
    lines.append(json.dumps(diag.get("cursor_source_article", {}), indent=2, ensure_ascii=False))
    lines.append("```\n")
    lines.append("**Response body snippet (httpx):**\n")
    lines.append("```")
    lines.append(diag.get("body_snippet_httpx", "(empty)"))
    lines.append("```\n")
    h_httpx = diag.get("resp_headers_httpx", {})
    lines.append("**Response headers — signals (httpx):**\n")
    lines.append("```json")
    lines.append(json.dumps(h_httpx, indent=2, ensure_ascii=False))
    lines.append("```\n")
    return lines


def _render_per_call_log(cursor_results: list) -> list:
    lines = ["### Per-Call Log\n"]
    lines.append("| Call | Status | Articles | Oldest-so-far | Elapsed | Error |")
    lines.append("|------|--------|----------|---------------|---------|-------|")
    call_rows_plain = [r for r in cursor_results
                       if isinstance(r.get("call"), int)]
    for r in call_rows_plain:
        s = r.get("status") or f"httpx={r.get('status_httpx')} curl={r.get('status_curl')}"
        lines.append(
            f"| {r['call']} | {s} | {r.get('articles', '—')} | "
            f"{r.get('oldest_so_far', '—')} | "
            f"{r.get('elapsed', '—')}s | {r.get('error') or '—'} |"
        )
    return lines


def _render_cursor_loop_section(cursor_results: list) -> list:
    lines = ["\n## Cursor Loop Results\n"]
    if not cursor_results:
        lines.append("_(no results — cursor extraction failed before first call)_\n")
        return lines

    summary = next((r for r in cursor_results if r.get("call") == "SUMMARY"), None)
    call_rows = [r for r in cursor_results if r.get("call") != "SUMMARY"]
    if summary:
        lines.extend(_render_cursor_summary(summary))

    diag = next((r for r in cursor_results if r.get("call") == "DIAG_403"), None)
    if diag:
        lines.extend(_render_403_diagnostics(diag))

    lines.extend(_render_per_call_log(cursor_results))
    return lines


def _render_rate_test_section(cursor_results_rate: list) -> list:
    lines = ["\n## Rate-Test Results (2s delay)\n"]
    summary_r = next((r for r in cursor_results_rate if r.get("call") == "SUMMARY"), None)
    if summary_r:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Successful calls | {summary_r['total_calls']} |")
        lines.append(f"| Non-200 | {summary_r['non_200']} |")
        lines.append(f"| Oldest date | {summary_r['oldest_date']} |")
        lines.append(f"| Avg elapsed | {summary_r['avg_elapsed']}s |\n")
    diag_r = next((r for r in cursor_results_rate if r.get("call") == "DIAG_403"), None)
    if diag_r:
        rec_r = diag_r.get("recoverability", {})
        lines.append(f"**403 still hit at 2s delay** — retry_at_10s={rec_r.get('retry_at_10s')} retry_at_40s={rec_r.get('retry_at_40s')}\n")
    else:
        lines.append("**No 403 encountered at 2s delay — rate-limit confirmed (time-based).**\n")
    return lines


# Write MD report with captured headers, replay status codes, cursor-loop results, and rate-test
def write_report(
    path: Path,
    ts: str,
    api_url: str | None,
    raw_headers: dict,
    replay_headers: dict,
    replay_results: dict,
    first_json_sample: dict | None,
    cursor_results: list | None,
    cursor_results_rate: list | None = None,
) -> None:
    lines = ["# CoinDesk Timeline API — HTTP Replay Probe"]
    lines.append(f"\n**Run:** {ts}\n")

    if api_url is None:
        lines.append("## Result: CAPTURE FAILED\n")
        lines.append(f"Timeline API (`{TIMELINE_API_PATH}`) did not appear in HAR entries after {CLICKS_TO_TRIGGER} clicks.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines += _render_captured_request(api_url)
    lines += _render_headers_section(raw_headers, replay_headers)
    lines += _render_replay_results(replay_results)
    lines += _render_json_sample(first_json_sample)

    if cursor_results is not None:
        lines += _render_cursor_loop_section(cursor_results)

    if cursor_results_rate is not None:
        lines += _render_rate_test_section(cursor_results_rate)

    path.write_text("\n".join(lines), encoding="utf-8")
