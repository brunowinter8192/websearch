#!/usr/bin/env python3
"""End-to-end Search→PDF chain probe: queries all engines, runs DIRECT/TIER1/MULTI_STEP download chain, saves PDFs to ~/Downloads."""

# INFRASTRUCTURE
import argparse
import asyncio
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.scraper.pdf_chain import (
    HARD_BLACKLIST,
    TIER1_DOMAINS,
    apply_tier1_transform,
    is_blacklisted,
    is_github_blob,
    parse_citation_pdf_url,
)
from src.search.browser import close_browser
from src.search.merge import build_engine_pools
from src.search.result import SearchResult
from src.search.search_web import _query_engines_concurrent, _select_engines

from _search_to_pdf_probe_config import DOMAIN_CONCURRENCY_CAP, DOWNLOAD_DIR, DOWNLOAD_TIMEOUT, MAX_CONNECTIONS
from _search_to_pdf_probe_report import _write_report

REPORT_DIR = SCRIPT_DIR / "md"

MAX_KEEPALIVE = 4
COURTESY_SLEEP = 0.5
HTML_READ_BYTES = 32 * 1024

USER_AGENT = "Mozilla/5.0 (compatible; research-probe/1.0)"


# ORCHESTRATOR

async def run_probe(queries: list[str], top_n: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    t_wall_start = time.monotonic()

    all_query_results: list[dict] = []

    limits = httpx.Limits(max_connections=MAX_CONNECTIONS, max_keepalive_connections=MAX_KEEPALIVE)
    async with httpx.AsyncClient(
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        try:
            for query in queries:
                print(f"\n=== {query!r} ===", file=sys.stderr)
                q_result = await _run_query(client, query, top_n)
                all_query_results.append(q_result)
        finally:
            await close_browser()

    wall_secs = time.monotonic() - t_wall_start
    report_path = _write_report(all_query_results, queries, top_n, wall_secs, ts, REPORT_DIR)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

# Search, merge, chain-download top_n results; return per-query dict with rows
async def _run_query(client: httpx.AsyncClient, query: str, top_n: int) -> dict:
    t0 = time.monotonic()

    selected, _ = _select_engines(None)
    print(f"  [search] engines={list(selected)}", file=sys.stderr)
    raw = await _query_engines_concurrent(query, "en", 100, selected)
    pools = build_engine_pools(raw)
    ranked = [r for pool in pools.values() for r in pool]
    candidates = ranked[:top_n]
    print(f"  [search] raw={len(raw)} merged={len(ranked)} top_n={len(candidates)}", file=sys.stderr)

    domain_sems: dict[str, asyncio.Semaphore] = {}
    rows: list[dict | None] = [None] * len(candidates)

    tasks = [
        _process_url_with_cap(client, result, rank + 1, domain_sems, rows, rank)
        for rank, result in enumerate(candidates)
    ]
    for coro in asyncio.as_completed(tasks):
        await coro

    return {
        "query": query,
        "rows": [r for r in rows if r is not None],
        "wall_secs": time.monotonic() - t0,
        "slot_counts": {e: len(p) for e, p in pools.items()},
    }


# Determine target domain for semaphore, acquire, process, release
async def _process_url_with_cap(
    client: httpx.AsyncClient,
    result: SearchResult,
    rank: int,
    domain_sems: dict[str, asyncio.Semaphore],
    rows: list,
    idx: int,
) -> None:
    url = result.url
    domain = _base_domain(url)
    chain_path, target_domain = _classify_chain_path(url, domain)

    if chain_path == "BLACKLIST":
        rows[idx] = _row(result, rank, "BLACKLIST", "BLACKLIST_SKIP", None, None)
        print(f"  [skip] {domain} (blacklist)", file=sys.stderr)
        return

    # For MULTI_STEP we can't know target domain upfront — Hop 1 first, sem after
    if chain_path == "MULTI_STEP":
        row = await _multistep_download(client, result, rank, domain_sems)
        rows[idx] = row
        return

    # DIRECT or TIER1: target domain is known
    if target_domain not in domain_sems:
        domain_sems[target_domain] = asyncio.Semaphore(DOMAIN_CONCURRENCY_CAP)
    async with domain_sems[target_domain]:
        if chain_path == "DIRECT":
            row = await _direct_download(client, result, rank, url)
        else:  # TIER1
            transformed = apply_tier1_transform(url)
            row = await _tier1_download(client, result, rank, transformed or url)
        await asyncio.sleep(COURTESY_SLEEP)
    rows[idx] = row


# Return (chain_path, target_domain) for a URL
def _classify_chain_path(url: str, domain: str) -> tuple[str, str]:
    if is_blacklisted(url) or is_github_blob(url):
        return "BLACKLIST", domain
    if domain in TIER1_DOMAINS or any(domain.endswith("." + t) for t in TIER1_DOMAINS):
        return "TIER1", domain
    if urlparse(url).path.lower().endswith(".pdf"):
        return "DIRECT", domain
    return "MULTI_STEP", domain


# DIRECT path: GET url as-is, save if PDF
async def _direct_download(client: httpx.AsyncClient, result: SearchResult, rank: int, url: str) -> dict:
    outcome, saved_name, saved_size = await _get_pdf_and_save(client, url)
    return _row(result, rank, "DIRECT", outcome, saved_name, saved_size)


# TIER1 path: apply transform, GET, save
async def _tier1_download(client: httpx.AsyncClient, result: SearchResult, rank: int, transformed_url: str) -> dict:
    outcome, saved_name, saved_size = await _get_pdf_and_save(client, transformed_url)
    return _row(result, rank, "TIER1", outcome, saved_name, saved_size)


# MULTI_STEP path: Hop 1 (extract citation_pdf_url), Hop 2 (download PDF)
async def _multistep_download(
    client: httpx.AsyncClient,
    result: SearchResult,
    rank: int,
    domain_sems: dict[str, asyncio.Semaphore],
) -> dict:
    url = result.url

    # Hop 1: GET HTML, extract citation_pdf_url
    citation_pdf_url = await _extract_citation_pdf_url(client, url)
    if citation_pdf_url is None:
        return _row(result, rank, "MULTI_STEP", "NO_PDF_LINK", None, None)

    # Hop 2: GET the citation PDF URL with per-host semaphore
    pdf_host = urlparse(citation_pdf_url).netloc
    if pdf_host not in domain_sems:
        domain_sems[pdf_host] = asyncio.Semaphore(DOMAIN_CONCURRENCY_CAP)
    async with domain_sems[pdf_host]:
        outcome, saved_name, saved_size = await _get_pdf_and_save(client, citation_pdf_url)
        await asyncio.sleep(COURTESY_SLEEP)

    return _row(result, rank, "MULTI_STEP", outcome, saved_name, saved_size)


# GET url, verify PDF, save to ~/Downloads; return (outcome, filename, size_bytes)
async def _get_pdf_and_save(client: httpx.AsyncClient, url: str) -> tuple[str, str | None, int | None]:
    try:
        body_chunks: list[bytes] = []
        filename: str | None = None
        ct_header = ""

        async with client.stream("GET", url, timeout=DOWNLOAD_TIMEOUT) as resp:
            if resp.status_code >= 400:
                return f"HTTP_{resp.status_code}", None, None

            ct_header = resp.headers.get("content-type", "").lower()
            filename = _extract_filename_from_resp(resp.headers, str(resp.url))

            async for chunk in resp.aiter_bytes(chunk_size=8192):
                body_chunks.append(chunk)

        body = b"".join(body_chunks)

        if not ("application/pdf" in ct_header or body[:4] == b"%PDF"):
            return "HTML_FALLBACK", None, None

        saved_path = _save_bytes(body, filename)
        return "DOWNLOADED", saved_path.name, saved_path.stat().st_size

    except httpx.TimeoutException:
        return "TIMEOUT", None, None
    except httpx.RequestError as e:
        return f"CONN_ERROR:{type(e).__name__}", None, None
    except Exception as e:
        return f"CONN_ERROR:{type(e).__name__}", None, None


# GET HTML from url, return extracted citation_pdf_url or None
async def _extract_citation_pdf_url(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        body_chunks: list[bytes] = []
        async with client.stream("GET", url, timeout=DOWNLOAD_TIMEOUT) as resp:
            if resp.status_code >= 400:
                return None
            ct = resp.headers.get("content-type", "").lower()
            if "text/html" not in ct:
                return None
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                body_chunks.append(chunk)
                if sum(len(c) for c in body_chunks) >= HTML_READ_BYTES:
                    break
        body_str = b"".join(body_chunks).decode("utf-8", errors="replace")
        return parse_citation_pdf_url(body_str)
    except Exception:
        return None


# Save bytes to ~/Downloads/<filename>, resolve name conflicts
def _save_bytes(data: bytes, filename: str) -> Path:
    dest = DOWNLOAD_DIR / filename
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = DOWNLOAD_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
    dest.write_bytes(data)
    return dest


# Extract filename from httpx response headers + URL (mirrors download_pdf.py logic)
def _extract_filename_from_resp(headers: httpx.Headers, url: str) -> str:
    cd = headers.get("content-disposition", "")
    if cd:
        m = re.search(r'filename[^;=\n]*=[\"\']?([^;\"\'\n]+)', cd)
        if m:
            name = m.group(1).strip()
            if name:
                return name
    path = url.split("?")[0].rstrip("/")
    basename = path.split("/")[-1]
    if basename and basename.lower().endswith(".pdf"):
        return basename
    return f"download_{int(time.time())}.pdf"


# Strip www. from netloc
def _base_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


# Build a result row dict
def _row(result: SearchResult, rank: int, chain_path: str, outcome: str,
         saved_name: str | None, saved_size: int | None) -> dict:
    return {
        "rank": rank,
        "url": result.url,
        "title": result.title,
        "engine": result.engine,
        "engines": result.engines,
        "chain_path": chain_path,
        "outcome": outcome,
        "saved_name": saved_name,
        "saved_size": saved_size,
    }



# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Search-to-PDF chain probe")
    p.add_argument("queries", nargs="+", help="One or more search queries")
    p.add_argument("--top-n", type=int, default=20, metavar="N",
                   help="Top-N URLs to attempt per query (default: 20)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run_probe(args.queries, args.top_n))
