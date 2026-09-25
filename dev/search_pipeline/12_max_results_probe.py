#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import median

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines.google import GoogleEngine
from src.search.engines.scholar import ScholarEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.browser import close_browser

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"

QUERIES = [
    "python asyncio",
    "tolkien hobbit",
    "sparse retrieval models",
]

ENGINE_MAX = {
    "google":         100,
    "google_scholar": 100,
    "duckduckgo":     200,
    "openalex":       200,
}

BROWSER_ENGINES = {"google", "google_scholar", "duckduckgo"}
BROWSER_SLEEP_S = 1.0
API_SLEEP_S = 0.5

ENGINE_NOTES = {
    "google":         "num= URL param; Google caps at 100 server-side",
    "google_scholar": "num= URL param; Scholar renders max ~20 per page",
    "duckduckgo":     "No count param; post-fetch slice only — page renders naturally",
    "openalex":       "per_page= API param; documented max 200",
}


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    engines = [
        ("google",         GoogleEngine()),
        ("google_scholar", ScholarEngine()),
        ("duckduckgo",     DuckDuckGoEngine()),
        ("openalex",       OpenAlexEngine()),
    ]

    records = []
    try:
        for engine_name, engine in engines:
            max_r = ENGINE_MAX[engine_name]
            sleep_s = BROWSER_SLEEP_S if engine_name in BROWSER_ENGINES else API_SLEEP_S
            print(f"\n=== {engine_name} (max_results={max_r}) ===", file=sys.stderr)
            for qi, query in enumerate(QUERIES):
                print(f"  [{qi + 1}/{len(QUERIES)}] {query!r}", file=sys.stderr, end="", flush=True)
                record = await probe_single(engine, engine_name, query, max_r)
                records.append(record)
                print(
                    f" → {record['status']} | {record['returned']} results | {record['latency_ms']}ms",
                    file=sys.stderr,
                )
                if qi < len(QUERIES) - 1:
                    await asyncio.sleep(sleep_s)
    finally:
        await close_browser()

    report_path = write_report(records, REPORT_DIR)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

async def probe_single(engine, engine_name: str, query: str, max_results: int) -> dict:
    record = {
        "engine":     engine_name,
        "query":      query,
        "requested":  max_results,
        "returned":   0,
        "latency_ms": 0,
        "status":     "ERROR",
    }
    t0 = time.monotonic()
    try:
        results = await engine.search(query, "en", max_results)
        record["latency_ms"] = round((time.monotonic() - t0) * 1000)
        record["returned"] = len(results)
        record["status"] = "OK" if results else "EMPTY"
    except Exception as e:
        record["latency_ms"] = round((time.monotonic() - t0) * 1000)
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return record


def write_report(records: list[dict], report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"max_results_probe_{ts}.md"
    summary = build_summary(records)

    lines = [
        f"# Max Results Per Call Probe — {ts}",
        "",
        "**Scope:** 8 engines × 3 queries, direct engine instantiation (bypasses `search_web_workflow` hardcoded cap of 10).",
        "**Per-engine max_results:** Google=100, Scholar=100, SE=100; DDG/Mojeek/Lobsters/OpenAlex/CrossRef=200.",
        "**Queries:** `python asyncio` · `tolkien hobbit` · `sparse retrieval models`",
        "",
        "## Detail Table",
        "",
        "| Engine | Query | Requested | Returned | Latency ms | Status |",
        "|--------|-------|-----------|----------|------------|--------|",
    ]
    for r in records:
        q = r["query"][:45].replace("|", "\\|")
        lines.append(
            f"| {r['engine']} | {q} | {r['requested']} | {r['returned']} | {r['latency_ms']} | {r['status']} |"
        )

    errors = [r for r in records if r.get("error")]
    if errors:
        lines += ["", "### Errors", ""]
        for r in errors:
            lines.append(f"- **{r['engine']} / {r['query'][:50]}:** {r['error']}")

    lines += [
        "",
        "## Per-Engine Summary",
        "",
        "| Engine | Requested | Ceiling (max returned) | Median latency ms | Notes |",
        "|--------|-----------|----------------------|-------------------|-------|",
    ]
    for eng, s in summary.items():
        lines.append(
            f"| {eng} | {s['requested']} | {s['ceiling']} | {s['median_latency_ms']} | {ENGINE_NOTES.get(eng, '')} |"
        )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_summary(records: list[dict]) -> dict[str, dict]:
    seen_order = list(dict.fromkeys(r["engine"] for r in records))
    summary = {}
    for eng in seen_order:
        eng_recs = [r for r in records if r["engine"] == eng]
        summary[eng] = {
            "requested":        eng_recs[0]["requested"],
            "ceiling":          max(r["returned"] for r in eng_recs),
            "median_latency_ms": round(median(r["latency_ms"] for r in eng_recs)),
        }
    return summary


if __name__ == "__main__":
    asyncio.run(run_probe())
