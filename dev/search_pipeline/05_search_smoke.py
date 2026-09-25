#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

import os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.browser import close_browser
from src.search.engines.google import GoogleEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.scholar import ScholarEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.result import SearchResult

SCRIPT_DIR = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR = SCRIPT_DIR / "md"

AVAILABLE_ENGINES = {
    "google": GoogleEngine,
    "duckduckgo": DuckDuckGoEngine,
    "google scholar": ScholarEngine,
    "openalex": OpenAlexEngine,
}


# ORCHESTRATOR

async def run_smoke(engine_names: list[str], max_queries: int | None) -> None:
    queries = _load_queries(QUERIES_FILE, max_queries)
    engines = {name: AVAILABLE_ENGINES[name]() for name in engine_names}
    print(f"Engines: {', '.join(engine_names)} | Queries: {len(queries)}", file=sys.stderr)

    records = []
    try:
        for qi, query in enumerate(queries):
            print(f"[{qi + 1}/{len(queries)}] {query}", file=sys.stderr)
            record = await _run_query(query, engines)
            records.append(record)
            print(
                f"  → urls={record['total_urls']} both={record['overlap']} "
                f"preview_ok={record['preview_ok']}/{record['total_urls']}",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = _write_report(records, engine_names)
    ok = sum(1 for r in records if r["total_urls"] > 0)
    print(f"\nReport: {path}", file=sys.stderr)
    print(f"Result: {ok}/{len(records)} queries with results", file=sys.stderr)


# FUNCTIONS

def _load_queries(path: Path, max_queries: int | None) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    qs = [l.strip() for l in lines if l.strip()]
    return qs[:max_queries] if max_queries else qs


async def _run_query(query: str, engines: dict) -> dict:
    tasks = [engine.search(query, "en", 10) for engine in engines.values()]
    per_engine = await asyncio.gather(*tasks, return_exceptions=True)

    merged: dict[str, dict] = {}
    for engine_name, results in zip(engines.keys(), per_engine):
        if isinstance(results, Exception):
            continue
        for r in results:
            if r.url not in merged:
                merged[r.url] = {"title": r.title, "snippets": {}, "preview": None}
            merged[r.url]["snippets"][engine_name] = r.snippet

    flat = [
        SearchResult(url=url, title=data["title"], snippet="", engine="", position=i)
        for i, (url, data) in enumerate(merged.items())
    ]
    flat_with_previews = flat

    preview_ok = 0
    for r in flat_with_previews:
        if r.preview and r.url in merged:
            merged[r.url]["preview"] = r.preview
            preview_ok += 1

    engine_counts = {}
    for engine_name, results in zip(engines.keys(), per_engine):
        engine_counts[engine_name] = len(results) if not isinstance(results, Exception) else 0

    overlap = sum(1 for data in merged.values() if len(data["snippets"]) > 1)

    return {
        "query": query,
        "merged": merged,
        "engine_counts": engine_counts,
        "total_urls": len(merged),
        "overlap": overlap,
        "preview_ok": preview_ok,
    }


def _write_report(records: list[dict], engine_names: list[str]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"search_smoke_{ts}.md"

    lines = _render_header(records, engine_names, ts)
    lines += _render_summary_table(records, engine_names)
    lines += ["", "---", ""]
    for qi, r in enumerate(records, 1):
        lines += _render_query_section(qi, r, engine_names)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_header(records: list[dict], engine_names: list[str], ts: str) -> list[str]:
    return [
        f"# Multi-Engine Search Smoke — {ts}",
        "",
        f"**Engines:** {', '.join(engine_names)}  ",
        f"**Queries:** {len(records)}  ",
        f"**Queries with results:** {sum(1 for r in records if r['total_urls'] > 0)}",
        "",
        "## Summary",
        "",
    ]


def _render_summary_table(records: list[dict], engine_names: list[str]) -> list[str]:
    engine_cols = " | ".join(f"{e.capitalize()}" for e in engine_names)
    header_sep = " | ".join("---" for _ in engine_names)
    lines = [
        f"| # | Query | {engine_cols} | Both | Total URLs | Preview OK |",
        f"|---|-------|{header_sep}|------|------------|------------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:50].replace("|", "\\|")
        engine_counts = " | ".join(str(r["engine_counts"].get(e, 0)) for e in engine_names)
        lines.append(
            f"| {i} | {q} | {engine_counts} | {r['overlap']} | {r['total_urls']} | {r['preview_ok']} |"
        )
    return lines


def _render_query_section(qi: int, r: dict, engine_names: list[str]) -> list[str]:
    lines = [f"## Query {qi}: {r['query']}", ""]

    if not r["merged"]:
        lines += ["*No results from any engine.*", ""]
        return lines

    lines += [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total URLs | {r['total_urls']} |",
    ]
    for e in engine_names:
        lines.append(f"| {e.capitalize()} results | {r['engine_counts'].get(e, 0)} |")
    lines += [
        f"| Found by both | {r['overlap']} |",
        f"| Preview fetched | {r['preview_ok']}/{r['total_urls']} |",
        "",
        "---",
        "",
    ]

    for idx, (url, data) in enumerate(r["merged"].items(), 1):
        lines += _render_url_entry(idx, url, data, engine_names)
    return lines


def _render_url_entry(idx: int, url: str, data: dict, engine_names: list[str]) -> list[str]:
    title = data["title"].replace("|", "\\|")
    engine_badges = " ".join(f"`{e}`" for e in sorted(data["snippets"].keys()))
    lines = [f"### [{idx}] {url}", f"**Title:** {title}  ", f"**Engines:** {engine_badges}", ""]

    for e in engine_names:
        if e in data["snippets"] and data["snippets"][e]:
            snip = data["snippets"][e][:400].replace("\n", " ")
            lines += [f"**Snippet [{e}]:**", snip, ""]
        elif e in data["snippets"]:
            lines += [f"**Snippet [{e}]:** *(empty)*", ""]

    if data["preview"]:
        og = data["preview"].get("og")
        meta = data["preview"].get("meta")
        if og:
            lines += [f"**Preview (og):** {og}", ""]
        if meta and meta != og:
            lines += [f"**Preview (meta):** {meta}", ""]
    else:
        lines += ["*(no preview)*", ""]

    lines.append("---")
    lines.append("")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-engine comparison smoke test.")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["google", "duckduckgo"],
        choices=list(AVAILABLE_ENGINES.keys()),
        help="Engines to test (default: google duckduckgo). Available: google duckduckgo 'google scholar' openalex",
    )
    parser.add_argument(
        "--max-queries",
        dest="max_queries",
        type=int,
        default=None,
        help="Limit to first N queries (default: all 30)",
    )
    args = parser.parse_args()
    asyncio.run(run_smoke(args.engines, args.max_queries))
