# INFRASTRUCTURE
from pathlib import Path


# FUNCTIONS

# Write final discovery report (MD)
def write_report(path: Path, results: dict, ts: str, stop_date: str) -> None:
    lines = ["# CoinDesk Full Discovery Report"]
    lines.append(f"\n**Run:** {ts} | **Stop date:** {stop_date}\n")
    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Successful cursor calls | {results['ok_calls']} |")
    lines.append(f"| Total articles written | {results['total_articles']} |")
    lines.append(f"| Oldest date reached | {results['oldest_date']} |")
    lines.append(f"| Avg elapsed / call | {results['avg_elapsed']}s |")
    wall = int(results.get("wall_seconds", 0))
    lines.append(f"| Wall-clock | {wall // 60}m {wall % 60}s |")
    lines.append(f"| Re-warm events | {results['rewarm_count']} |")
    lines.append(f"| Fallback-cursor activations | {results['fallback_count']} |")
    rewarm_method = (
        "httpx feedpage GET ✅" if results.get("httpx_rewarm_confirmed") is True
        else "browser required ❌ (httpx insufficient)" if results.get("httpx_rewarm_confirmed") is False
        else "not triggered (no warmth-related 403 encountered)"
    )
    lines.append(f"| Re-warm method determination | {rewarm_method} |\n")

    lines.append("## Per-Year Article Counts\n")
    lines.append("| Year | Articles | File |")
    lines.append("|------|----------|------|")
    for year in sorted(results["year_counts"].keys(), reverse=True):
        cnt = results["year_counts"][year]
        lines.append(f"| {year} | {cnt} | `urls/coindesk_{year}.txt` |")

    path.write_text("\n".join(lines), encoding="utf-8")
