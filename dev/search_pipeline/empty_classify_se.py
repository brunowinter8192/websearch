#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

REPORT_DIR = SCRIPT_DIR / "md"
API_URL = "https://api.stackexchange.com/2.3/search/advanced"

SE_EMPTY_QUERIES = [
    (3,  "fastapi websocket reconnect handler"),
    (10, "RLHF reinforcement learning human feedback"),
    (12, "RAG retrieval augmented generation benchmark"),
    (13, "climate change carbon capture technology 2025"),
    (14, "epidemiology cohort study design methodology"),
    (15, "Bewerbung Lebenslauf Format Deutschland"),
    (16, "Mietvertrag Kündigungsfrist gesetzliche Regelung"),
    (17, "GmbH Gründung Kosten Schritte"),
    (18, "Krankenversicherung Vergleich gesetzlich privat"),
    (19, "Python Programmierung Anfänger Tutorial deutsch"),
    (21, "crawl4ai stealth browser detection bypass"),
    (22, "pydoll chromium CDP automation"),
    (24, "trafilatura vs readability content extraction"),
    (25, "SPLADE sparse retrieval model implementation"),
    (29, "kubernetes vs docker swarm comparison"),
]

BASE_PARAMS = {
    "pagesize": 10,
    "sort": "relevance",
    "order": "desc",
    "filter": "withbody",
}


# ORCHESTRATOR

async def run_classify() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for idx, (smoke_row, query) in enumerate(SE_EMPTY_QUERIES):
            print(f"[{idx + 1}/15] smoke#{smoke_row}: {query}", file=sys.stderr)
            record = await probe_query(client, smoke_row, query)
            records.append(record)
            label = record["classification"]
            print(
                f"  SO items={record['so_items']} total={record['so_total']} | "
                f"XS items={record['xs_items']} total={record['xs_total']} | {label}",
                file=sys.stderr,
            )
            if idx < len(SE_EMPTY_QUERIES) - 1:
                await asyncio.sleep(1.0)

    report_path = write_report(records)
    counts = _summary_counts(records)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Summary: {counts}", file=sys.stderr)


# FUNCTIONS

async def probe_query(client: httpx.AsyncClient, smoke_row: int, query: str) -> dict:
    record = _new_record(smoke_row, query)

    if await _probe_stackoverflow(client, query, record):
        return record

    await asyncio.sleep(1.0)

    await _probe_cross_site(client, query, record)

    record["classification"] = _classify(record)
    return record


def _new_record(smoke_row: int, query: str) -> dict:
    return {
        "smoke_row": smoke_row,
        "query": query,
        "so_http": None,
        "so_total": None,
        "so_items": None,
        "so_has_more": None,
        "quota_remaining": None,
        "xs_http": None,
        "xs_total": None,
        "xs_items": None,
        "classification": "UNKNOWN",
        "notes": "",
    }


async def _probe_stackoverflow(client: httpx.AsyncClient, query: str, record: dict) -> bool:
    so_params = {**BASE_PARAMS, "q": query, "site": "stackoverflow"}
    try:
        resp = await client.get(API_URL, params=so_params)
        record["so_http"] = resp.status_code
        if resp.status_code in (429, 403):
            record["classification"] = "RATE_LIMITED"
            record["notes"] = f"SO returned HTTP {resp.status_code}"
            return True
        if resp.status_code == 200:
            data = resp.json()
            record["so_total"] = data.get("total", 0)
            record["so_items"] = len(data.get("items", []))
            record["so_has_more"] = data.get("has_more", False)
            record["quota_remaining"] = data.get("quota_remaining")
    except Exception as e:
        record["notes"] = f"SO request error: {e}"
        return True
    return False


async def _probe_cross_site(client: httpx.AsyncClient, query: str, record: dict) -> None:
    xs_params = {**BASE_PARAMS, "q": query, "site": "stackexchange"}
    try:
        resp = await client.get(API_URL, params=xs_params)
        record["xs_http"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            record["xs_total"] = data.get("total", 0)
            record["xs_items"] = len(data.get("items", []))
            if data.get("quota_remaining") is not None:
                record["quota_remaining"] = data["quota_remaining"]
    except Exception as e:
        record["notes"] += f" | XS request error: {e}"


def _classify(r: dict) -> str:
    if r["so_http"] in (429, 403):
        return "RATE_LIMITED"
    if r["so_http"] != 200:
        return "UNKNOWN"
    so_items = r["so_items"] or 0
    xs_items = r["xs_items"] or 0
    if so_items > 0:
        return "PIPELINE_BUG"
    if so_items == 0 and xs_items > 0:
        return "ENGINE_NICHE"
    if so_items == 0 and xs_items == 0:
        return "ENGINE_EMPTY"
    return "UNKNOWN"


def _summary_counts(records: list[dict]) -> dict:
    counts = {"ENGINE_EMPTY": 0, "ENGINE_NICHE": 0, "PIPELINE_BUG": 0, "RATE_LIMITED": 0, "BOT_BLOCK": 0, "UNKNOWN": 0}
    for r in records:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    return counts


def write_report(records: list[dict]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"empty_classify_se_{ts}.md"
    counts = _summary_counts(records)

    lines = [
        f"# StackEx EMPTY Classification — {ts}",
        "",
        "Source: `dev/search_pipeline/md/search_smoke_20260504_023641.md`",
        "Method: direct httpx probe against api.stackexchange.com/2.3/search/advanced, anonymous quota.",
        "",
        "## Summary",
        "",
        f"- ENGINE_EMPTY: {counts['ENGINE_EMPTY']}/15",
        f"- ENGINE_NICHE: {counts['ENGINE_NICHE']}/15",
        f"- PIPELINE_BUG: {counts['PIPELINE_BUG']}/15",
        f"- RATE_LIMITED: {counts['RATE_LIMITED']}/15",
        f"- BOT_BLOCK: {counts['BOT_BLOCK']}/15",
        f"- UNKNOWN: {counts['UNKNOWN']}/15",
        "",
        "## Per-Query",
        "",
        "| # | Smoke # | Query | HTTP | SO total | SO items | XS total | XS items | quota_left | Classification |",
        "|---|---------|-------|------|----------|----------|----------|----------|------------|----------------|",
    ]

    for idx, r in enumerate(records, 1):
        query = r["query"].replace("|", "\\|")
        lines.append(
            f"| {idx} | {r['smoke_row']} | {query} | {r['so_http']} "
            f"| {r['so_total']} | {r['so_items']} "
            f"| {r['xs_total']} | {r['xs_items']} "
            f"| {r['quota_remaining']} | {r['classification']} |"
        )

    noted = [r for r in records if r.get("notes")]
    if noted:
        lines += ["", "## Notes", ""]
        for r in noted:
            lines.append(f"- Smoke#{r['smoke_row']} `{r['query']}`: {r['notes']}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    asyncio.run(run_classify())
