#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "01_reports"
API_URL = "https://api.openalex.org/works"
PER_PAGE = 100
TOP_N = 10
INTER_QUERY_DELAY_S = 1.0

QUERIES = [
    "WHO environmental noise guidelines European Region 2018",
    "WHO Night Noise Guidelines for Europe 2009 pdf",
    "Basner McGuire systematic review environmental noise effects on sleep 2018",
    "iris.who.int environmental noise guidelines European region 2018 download",
    "Basner McGuire 2018 IJERPH 15 519 sleep pdf full text",
    "web content extraction quality evaluation benchmark",
    "clothing lifespan wears per garment replacement rate study",
]

EYEBALL_QUERY_NUMS = {3, 6}


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    error = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for qi, query in enumerate(QUERIES, 1):
            print(f"[{qi}/{len(QUERIES)}] {query}", file=sys.stderr)
            try:
                works = await fetch_works(client, query)
            except RateLimitError as e:
                print(f"  -> 429 STOP: {e}", file=sys.stderr)
                error = str(e)
                break
            record = build_record(qi, query, works)
            records.append(record)
            print(
                f"  -> total={record['total']} pdf={record['pdf_url']} "
                f"landing={record['landing_only']} no_oa={record['no_oa']}",
                file=sys.stderr,
            )
            if qi < len(QUERIES):
                await asyncio.sleep(INTER_QUERY_DELAY_S)

    report_path = write_report(records, error)
    print(f"\nReport: {report_path}", file=sys.stderr)
    if error:
        print(f"Stopped early: {error}", file=sys.stderr)


# FUNCTIONS

async def fetch_works(client: httpx.AsyncClient, query: str) -> list[dict]:
    params = {"search": query, "per_page": PER_PAGE}
    response = await client.get(API_URL, params=params)
    if response.status_code == 429:
        raise RateLimitError(f"429 for query: {query}")
    response.raise_for_status()
    return response.json().get("results", [])


def build_record(qi: int, query: str, works: list[dict]) -> dict:
    labels_full = [classify(w) for w in works]
    labels_top10 = labels_full[:TOP_N]
    type_counter_full = Counter(
        (w.get("type") or "unknown") for w, lbl in zip(works, labels_full) if lbl == "pdf_url"
    )
    record = {
        "qi": qi,
        "query": query,
        "total": len(works),
        "pdf_url": labels_full.count("pdf_url"),
        "landing_only": labels_full.count("landing_only"),
        "no_oa": labels_full.count("no_oa"),
        "top10_total": len(labels_top10),
        "top10_pdf_url": labels_top10.count("pdf_url"),
        "top10_landing_only": labels_top10.count("landing_only"),
        "top10_no_oa": labels_top10.count("no_oa"),
        "type_breakdown": type_counter_full,
        "eyeball": build_eyeball_rows(works[:TOP_N]) if qi in EYEBALL_QUERY_NUMS else None,
    }
    return record


def write_report(records: list[dict], error: str | None) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"openalex_pdf_probe_{ts}.md"

    lines = [
        f"# OpenAlex PDF-URL Availability Probe (Milestone 1) — {ts}",
        "",
        "Measurement only — no src/ touched, no wiring. Direct httpx against "
        "`https://api.openalex.org/works?search=<q>&per_page=100`, no `mailto`, no API key.",
        "",
    ]
    if error:
        lines += [f"**Stopped early due to: {error}**", ""]

    lines += _build_per_query_table(records)
    lines += _build_type_breakdown_section(records)
    lines += _build_eyeball_section(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class RateLimitError(Exception):
    pass


def classify(work: dict) -> str:
    loc = work.get("best_oa_location")
    if loc is None:
        return "no_oa"
    if loc.get("pdf_url"):
        return "pdf_url"
    return "landing_only"


def build_eyeball_rows(works: list[dict]) -> list[dict]:
    rows = []
    for w in works:
        loc = w.get("best_oa_location") or {}
        rows.append({
            "title": (w.get("title") or "")[:100],
            "type": w.get("type") or "unknown",
            "chosen_url": _pick_url(w),
            "pdf_url": loc.get("pdf_url") or "",
        })
    return rows


def _build_per_query_table(records: list[dict]) -> list[str]:
    lines = [
        "## Per-Query Counts",
        "",
        "| # | Query | Total | pdf_url | landing-only | no OA | Top-10 total | Top-10 pdf_url | Top-10 landing-only | Top-10 no OA |",
        "|---|-------|------:|--------:|--------------:|------:|--------------:|----------------:|----------------------:|--------------:|",
    ]
    sum_total = sum_pdf = sum_landing = sum_no_oa = 0
    sum_t10_total = sum_t10_pdf = sum_t10_landing = sum_t10_no_oa = 0
    for r in records:
        q = r["query"][:60].replace("|", "\\|")
        lines.append(
            f"| {r['qi']} | {q} | {r['total']} | {r['pdf_url']} | {r['landing_only']} | {r['no_oa']} "
            f"| {r['top10_total']} | {r['top10_pdf_url']} | {r['top10_landing_only']} | {r['top10_no_oa']} |"
        )
        sum_total += r["total"]
        sum_pdf += r["pdf_url"]
        sum_landing += r["landing_only"]
        sum_no_oa += r["no_oa"]
        sum_t10_total += r["top10_total"]
        sum_t10_pdf += r["top10_pdf_url"]
        sum_t10_landing += r["top10_landing_only"]
        sum_t10_no_oa += r["top10_no_oa"]
    lines.append(
        f"| **All** | | **{sum_total}** | **{sum_pdf}** | **{sum_landing}** | **{sum_no_oa}** "
        f"| **{sum_t10_total}** | **{sum_t10_pdf}** | **{sum_t10_landing}** | **{sum_t10_no_oa}** |"
    )
    lines.append("")
    return lines


def _build_type_breakdown_section(records: list[dict]) -> list[str]:
    lines = ["## Type Breakdown of pdf_url-Present Works (full result set)", ""]
    for r in records:
        lines.append(f"**Q{r['qi']}** `{r['query'][:60]}`: " + (
            ", ".join(f"{t}={c}" for t, c in sorted(r["type_breakdown"].items(), key=lambda x: -x[1]))
            if r["type_breakdown"] else "(none)"
        ))
    lines.append("")
    return lines


def _build_eyeball_section(records: list[dict]) -> list[str]:
    lines = ["## Eyeball: First 10 Results — Chosen URL vs best_oa_location.pdf_url", ""]
    for r in records:
        if r["eyeball"] is None:
            continue
        lines.append(f"### Q{r['qi']}: `{r['query']}`")
        lines.append("")
        lines.append("| # | Title | Type | Chosen URL (_pick_url) | best_oa_location.pdf_url |")
        lines.append("|---|-------|------|-------------------------|---------------------------|")
        for i, row in enumerate(r["eyeball"], 1):
            title = row["title"].replace("|", "\\|")
            lines.append(f"| {i} | {title} | {row['type']} | {row['chosen_url']} | {row['pdf_url']} |")
        lines.append("")
    return lines


def _pick_url(work: dict) -> str:
    ids = work.get("ids") or {}
    arxiv = ids.get("arxiv")
    if arxiv:
        return arxiv
    doi = work.get("doi")
    if doi:
        return doi
    return work.get("id", "")


if __name__ == "__main__":
    asyncio.run(run_probe())
