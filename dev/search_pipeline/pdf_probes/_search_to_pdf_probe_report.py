# INFRASTRUCTURE
from collections import Counter, defaultdict
from pathlib import Path

from _search_to_pdf_probe_config import DOMAIN_CONCURRENCY_CAP, DOWNLOAD_DIR, DOWNLOAD_TIMEOUT, MAX_CONNECTIONS


# FUNCTIONS

def _write_report(
    all_query_results: list[dict],
    queries: list[str],
    top_n: int,
    wall_secs: float,
    ts: str,
    report_dir: Path,
) -> Path:
    path = report_dir / f"search_to_pdf_{ts}.md"
    path.write_text("\n".join(_build_report(all_query_results, queries, top_n, wall_secs, ts)), encoding="utf-8")
    return path


def _build_report(
    all_query_results: list[dict],
    queries: list[str],
    top_n: int,
    wall_secs: float,
    ts: str,
) -> list[str]:
    lines: list[str] = [f"# Search-to-PDF Chain Probe — {ts}", ""]
    lines += _section_metadata(all_query_results, queries, top_n, wall_secs, ts)
    lines += _section_per_query_summary(all_query_results)
    lines += _section_per_query_detail(all_query_results)
    lines += _section_path_distribution(all_query_results)
    lines += _section_highlights(all_query_results)
    return lines


def _section_metadata(
    all_query_results: list[dict],
    queries: list[str],
    top_n: int,
    wall_secs: float,
    ts: str,
) -> list[str]:
    minutes, secs = divmod(int(wall_secs), 60)
    all_rows = [r for q in all_query_results for r in q["rows"]]
    downloaded = [r for r in all_rows if r["outcome"] == "DOWNLOADED"]
    total_bytes = sum(r["saved_size"] for r in downloaded if r["saved_size"])
    size_str = f"{total_bytes / 1024 / 1024:.1f} MB" if total_bytes >= 1024 * 1024 else f"{total_bytes / 1024:.1f} KB"
    return [
        "## Section 1 — Run Metadata",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Timestamp | {ts} |",
        f"| Queries | {len(queries)} |",
        f"| Top-N per query | {top_n} |",
        f"| Wall clock | {minutes}m {secs}s |",
        f"| Download directory | {DOWNLOAD_DIR} |",
        f"| Total PDFs downloaded | {len(downloaded)} |",
        f"| Total disk usage | {size_str} |",
        f"| Timeout per request | {DOWNLOAD_TIMEOUT}s |",
        f"| Concurrency | global_max={MAX_CONNECTIONS}, per_domain_cap={DOMAIN_CONCURRENCY_CAP} |",
        "",
    ]


def _section_per_query_summary(all_query_results: list[dict]) -> list[str]:
    lines = [
        "## Section 2 — Per-Query Summary Table",
        "",
        "| Query | URLs | Downloaded | Blacklist | No PDF Link | HTML Fallback | HTTP 4xx | Timeout | Other | Wall (s) |",
        "|-------|-----:|-----------:|----------:|------------:|--------------:|---------:|--------:|------:|---------:|",
    ]
    for q in all_query_results:
        rows = q["rows"]
        c: dict[str, int] = defaultdict(int)
        for r in rows:
            c[r["outcome"]] += 1
        http4xx = sum(v for k, v in c.items() if k.startswith("HTTP_4"))
        timeout = c.get("TIMEOUT", 0)
        other = sum(v for k, v in c.items() if k not in ("DOWNLOADED", "BLACKLIST_SKIP", "NO_PDF_LINK", "HTML_FALLBACK", "TIMEOUT") and not k.startswith("HTTP_4"))
        label = q["query"][:50].replace("|", " ")
        lines.append(
            f"| {label} | {len(rows)} | {c.get('DOWNLOADED', 0)} | "
            f"{c.get('BLACKLIST_SKIP', 0)} | {c.get('NO_PDF_LINK', 0)} | "
            f"{c.get('HTML_FALLBACK', 0)} | {http4xx} | {timeout} | {other} | "
            f"{q['wall_secs']:.0f} |"
        )
    lines.append("")
    return lines


def _section_per_query_detail(all_query_results: list[dict]) -> list[str]:
    lines = ["## Section 3 — Per-Query Per-URL Detail", ""]
    for q in all_query_results:
        lines += [f"### {q['query']}", ""]
        lines += [
            "| Rank | Original URL | Chain Path | Outcome | Saved File |",
            "|-----:|-------------|:----------:|---------|------------|",
        ]
        for r in q["rows"]:
            url = r["url"][:80].replace("|", "%7C")
            fname = r["saved_name"] or "—"
            lines.append(
                f"| {r['rank']} | {url} | {r['chain_path']} | {r['outcome']} | {fname} |"
            )
        lines.append("")
    return lines


def _section_path_distribution(all_query_results: list[dict]) -> list[str]:
    all_rows = [r for q in all_query_results for r in q["rows"]]
    by_path: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        by_path[r["chain_path"]].append(r)

    lines = [
        "## Section 4 — Aggregate Path Distribution",
        "",
        "| Chain Path | Total URLs | DOWNLOADED | Success % | Top Outcomes |",
        "|:----------:|-----------:|-----------:|----------:|--------------|",
    ]
    for path in ("DIRECT", "TIER1", "MULTI_STEP", "BLACKLIST"):
        rows = by_path.get(path, [])
        if not rows:
            continue
        downloaded = sum(1 for r in rows if r["outcome"] == "DOWNLOADED")
        pct = f"{100 * downloaded / len(rows):.0f}%" if rows else "—"
        c: dict[str, int] = defaultdict(int)
        for r in rows:
            c[r["outcome"]] += 1
        top = ", ".join(f"{k}={v}" for k, v in sorted(c.items(), key=lambda x: -x[1])[:4])
        lines.append(f"| {path} | {len(rows)} | {downloaded} | {pct} | {top} |")
    lines.append("")
    return lines


def _section_highlights(all_query_results: list[dict]) -> list[str]:
    all_rows = [r for q in all_query_results for r in q["rows"]]
    downloaded = [r for r in all_rows if r["outcome"] == "DOWNLOADED"]

    total_bytes = sum(r["saved_size"] for r in downloaded if r["saved_size"])
    size_str = f"{total_bytes / 1024 / 1024:.1f} MB" if total_bytes >= 1024 * 1024 else f"{total_bytes / 1024:.1f} KB"

    engine_counts: Counter = Counter()
    for r in downloaded:
        for eng in (r["engines"] or [r["engine"]]):
            engine_counts[eng] += 1
    top3_engines = engine_counts.most_common(3)

    lines = [
        "## Section 5 — Summary Highlights",
        "",
        f"- **Total PDFs downloaded:** {len(downloaded)}",
        f"- **Total disk usage:** {size_str}",
        f"- **Downloadable rate:** {100 * len(downloaded) / len(all_rows):.1f}% of all candidate URLs" if all_rows else "- **Downloadable rate:** —",
        "",
        "**Top 3 contributing engines (by downloaded URL count):**",
        "",
        "| Engine | Downloaded URLs contributed |",
        "|--------|---------------------------:|",
    ]
    for eng, cnt in top3_engines:
        lines.append(f"| {eng} | {cnt} |")
    if not top3_engines:
        lines.append("| (none) | 0 |")

    lines += [
        "",
        "**Downloaded files:**",
        "",
        "| Filename | Size | Source URL |",
        "|----------|-----:|------------|",
    ]
    for r in downloaded:
        size_kb = f"{r['saved_size'] / 1024:.1f} KB" if r["saved_size"] else "?"
        src = r["url"][:70].replace("|", "%7C")
        lines.append(f"| {r['saved_name']} | {size_kb} | {src} |")
    lines.append("")
    return lines
