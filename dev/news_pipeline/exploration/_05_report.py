# INFRASTRUCTURE
import json
from pathlib import Path


# FUNCTIONS
def _render_walk_header(ts: str, api_url: str, n: int, results: dict) -> list:
    lines = ["# CoinDesk StoryType Walk Report"]
    lines.append(f"\n**Run:** {ts} | **Max calls:** {n}\n")
    lines.append(f"**Start URL:** `{api_url}`\n")
    lines.append(f"**Total articles logged:** {results['total_articles']}\n")
    return lines


def _render_type_distribution(results: dict) -> list:
    lines = ["## StoryType Distribution\n"]
    lines.append("| storyType | Count | % |")
    lines.append("|-----------|-------|---|")
    total = results["total_articles"]
    for st, cnt in results["type_distribution"].items():
        pct = round(cnt / total * 100, 1) if total else 0
        lines.append(f"| `{st}` | {cnt} | {pct}% |")
    return lines


def _render_target_section(results: dict) -> list:
    lines = ["\n## Target Article (cc8f264d)\n"]
    target = results.get("target_article")
    if target:
        lines.append("✅ **FOUND**\n")
        lines.append("```json")
        lines.append(json.dumps(target, indent=2, ensure_ascii=False))
        lines.append("```\n")
    else:
        lines.append("⚠️ TARGET NOT ENCOUNTERED in walk responses.\n")
    return lines


def _render_walk_call_row(r: dict) -> list:
    lines = []
    if "error" in r and "status" not in r:
        lines.append(f"| {r['call']} | ERROR | — | — | — | {r['error']} | — |")
        return lines
    if r.get("status", 200) != 200:
        flag = "✅ **TARGET**" if r.get("target_in_call") else "—"
        lines.append(
            f"| {r['call']} | **{r['status']}** | — | — |"
            f" {r.get('oldest','')[:10]} | {flag} | {r.get('elapsed','?')}s |"
        )
        cs = r.get("cursor_source", {})
        if cs:
            lines.append(f"\n**403 cursor source:**")
            lines.append(f"- `_id`: `{cs.get('_id')}`")
            lines.append(f"- `storyType`: `{cs.get('storyType')}`")
            lines.append(f"- `displayDate`: {cs.get('displayDate')}")
            lines.append(f"- `pathname`: {cs.get('pathname')}")
            lines.append(f"- `title`: {cs.get('title')}")
        snip = r.get("body_snippet", "")
        if snip:
            lines.append(f"\n**403 body snippet:**\n```\n{snip}\n```\n")
    else:
        flag = "✅ **TARGET**" if r.get("target_in_call") else "—"
        lines.append(
            f"| {r['call']} | 200 | {r.get('count','—')} |"
            f" {r.get('newest','')[:10]} | {r.get('oldest','')[:10]} |"
            f" {flag} | {r.get('elapsed','?')}s |"
        )
    return lines


def _render_walk_call_log(results: dict) -> list:
    lines = ["## Call Log\n"]
    lines.append("| Call | Status | Count | Newest | Oldest | Target? | Elapsed |")
    lines.append("|------|--------|-------|--------|--------|---------|---------|")
    for r in results["call_log"]:
        lines.extend(_render_walk_call_row(r))
    return lines


def write_walk_report(report_path: Path, articles_path: Path, ts: str, api_url: str, n: int, results: dict) -> None:
    lines = []
    lines += _render_walk_header(ts, api_url, n, results)
    lines += _render_type_distribution(results)
    lines += _render_target_section(results)
    lines += _render_walk_call_log(results)

    report_path.write_text("\n".join(lines), encoding="utf-8")
    articles_path.write_text(
        json.dumps(results["all_articles"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _render_fixed_header(ts: str, api_url: str, n: int, invalid_types: frozenset) -> list:
    lines = ["# CoinDesk Fixed Cursor Loop Report"]
    lines.append(f"\n**Run:** {ts} | **Max calls:** {n}\n")
    lines.append(f"**Start URL:** `{api_url}`\n")
    lines.append(f"**Invalid anchor types (skipped):** `{sorted(invalid_types) or '(none)'}`\n")
    return lines


def _render_fixed_summary(results: list) -> list:
    summary = next((r for r in results if r.get("call") == "SUMMARY"), None)
    if not summary:
        return []
    lines = ["## Summary\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Successful calls | {summary['total_calls']} |")
    lines.append(f"| Total articles | {summary['total_articles']} |")
    lines.append(f"| Oldest date reached | {summary['oldest_date']} |")
    lines.append(f"| Avg elapsed / call | {summary['avg_elapsed']}s |")
    lines.append(f"| Cursor-fix overrides | {summary['cursor_fixed_count']} |")
    lines.append(f"| Non-200 responses | {summary['non_200']} |\n")
    return lines


def _render_fixed_call_row(r: dict) -> list:
    lines = []
    fix_flag = "✅" if r.get("cursor_fixed") else "—"
    skipped = r.get("skipped_storyType") or "—"
    if r.get("status") != 200:
        lines.append(
            f"| {r['call']} | **{r['status']}** | — |"
            f" {r.get('anchor_storyType','?')} | {fix_flag} | {skipped} |"
            f" {r.get('oldest_so_far','?')} | {r.get('elapsed','?')}s |"
        )
        snip = r.get("body_snippet", "")
        if snip:
            lines.append(f"\n**Error body:**\n```\n{snip}\n```\n")
    else:
        lines.append(
            f"| {r['call']} | 200 | {r.get('articles','—')} |"
            f" {r.get('anchor_storyType','?')} | {fix_flag} | {skipped} |"
            f" {r.get('oldest_so_far','?')} | {r.get('elapsed','?')}s |"
        )
    return lines


def _render_fixed_call_log(results: list) -> list:
    lines = ["## Per-Call Log\n"]
    lines.append("| Call | Status | Articles | Anchor type | Fixed? | Skipped type | Oldest | Elapsed |")
    lines.append("|------|--------|----------|-------------|--------|--------------|--------|---------|")
    for r in results:
        if r.get("call") == "SUMMARY":
            continue
        lines.extend(_render_fixed_call_row(r))
    return lines


def write_fixed_report(report_path: Path, ts: str, api_url: str, n: int, invalid_types: frozenset, results: list) -> None:
    lines = []
    lines += _render_fixed_header(ts, api_url, n, invalid_types)
    lines += _render_fixed_summary(results)
    lines += _render_fixed_call_log(results)
    report_path.write_text("\n".join(lines), encoding="utf-8")
