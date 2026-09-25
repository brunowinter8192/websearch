#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from _citation_pdf_followup_config import (
    DOMAIN_CONCURRENCY_CAP, DOMAIN_COURTESY_SLEEP, GLOBAL_MAX_CONNECTIONS, HOP_TIMEOUT, SOURCE_REPORT,
)
from _citation_pdf_followup_report import _write_report

SCRIPT_DIR = Path(__file__).parent.parent
REPORT_DIR = SCRIPT_DIR / "md"
DATA_DIR = SCRIPT_DIR / "txt"

SOURCE_POOL = "pool_20260507_172709.txt"

GLOBAL_MAX_KEEPALIVE = 4
HTML_READ_BYTES = 32 * 1024

CITATION_PDF_META_RE = re.compile(
    r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
    re.IGNORECASE,
)


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    pool = _load_pool()
    _write_pool_file(pool, ts)
    _print_pool_html_has(pool)

    t_start = time.monotonic()
    results = await _probe_all(pool)
    wall_secs = _compute_wall_secs(t_start)

    report_path = _write_report(results, wall_secs, ts, REPORT_DIR)
    _print_report(report_path)


# FUNCTIONS

def _load_pool() -> list[str]:
    report_path = REPORT_DIR / SOURCE_REPORT
    pool_path = DATA_DIR / SOURCE_POOL

    report_text = report_path.read_text(encoding="utf-8")
    pool_urls = set(pool_path.read_text(encoding="utf-8").splitlines())
    pool_urls.discard("")

    urls: list[str] = []
    in_s6 = False
    for line in report_text.splitlines():
        if "## Section 6" in line:
            in_s6 = True
            continue
        if in_s6 and line.startswith("## Section"):
            break
        if not in_s6 or not line.startswith("| "):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 7 or parts[5] != "HTML_HAS_PDF_LINK":
            continue
        url_part = parts[3]
        if url_part in pool_urls:
            urls.append(url_part)
        else:
            matches = [u for u in pool_urls if u.startswith(url_part)]
            if len(matches) == 1:
                urls.append(matches[0])
            else:
                print(f"[pool] WARNING: could not resolve {url_part!r} → skipped", file=sys.stderr)

    return urls


def _write_pool_file(pool: list[str], ts: str) -> None:
    path = DATA_DIR / f"pool_has_pdf_link_{ts}.txt"
    path.write_text("\n".join(pool) + "\n", encoding="utf-8")
    print(f"[pool] written: {path.name}", file=sys.stderr)


def _print_pool_html_has(pool):
    print(f"[pool] {len(pool)} HTML_HAS_PDF_LINK URLs loaded", file=sys.stderr)


async def _probe_all(pool: list[str]) -> list[dict]:
    limits = httpx.Limits(max_connections=GLOBAL_MAX_CONNECTIONS, max_keepalive_connections=GLOBAL_MAX_KEEPALIVE)
    domain_sems: dict[str, asyncio.Semaphore] = {}
    results: list[dict | None] = [None] * len(pool)

    async with httpx.AsyncClient(
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; research-probe/1.0)"},
    ) as client:
        tasks = [
            _probe_with_cap(client, url, idx, domain_sems, results)
            for idx, url in enumerate(pool)
        ]
        done = 0
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 20 == 0 or done == total:
                print(f"[probe] {done}/{total}", file=sys.stderr)

    return [r for r in results if r is not None]


def _compute_wall_secs(t_start):
    wall_secs = time.monotonic() - t_start
    return wall_secs


def _print_report(report_path):
    print(f"\nReport: {report_path}", file=sys.stderr)


async def _probe_with_cap(
    client: httpx.AsyncClient,
    url: str,
    idx: int,
    domain_sems: dict[str, asyncio.Semaphore],
    results: list,
) -> None:
    hop1 = await _hop1_extract(client, url)

    if hop1["citation_pdf_url"] is None:
        results[idx] = {
            "original_url": url,
            "original_domain": _base_domain(url),
            "citation_pdf_url": None,
            "pdf_host_domain": None,
            "hop2_outcome": "EXTRACTION_FAILED",
            "hop2_status": None,
            "hop2_content_type": None,
            "hop2_title": None,
            "hop2_body_preview": None,
            "hop1_outcome": hop1["outcome"],
        }
        return

    pdf_url = hop1["citation_pdf_url"]
    pdf_domain = urlparse(pdf_url).netloc

    if pdf_domain not in domain_sems:
        domain_sems[pdf_domain] = asyncio.Semaphore(DOMAIN_CONCURRENCY_CAP)
    async with domain_sems[pdf_domain]:
        hop2 = await _hop2_classify(client, pdf_url)
        await asyncio.sleep(DOMAIN_COURTESY_SLEEP)

    results[idx] = {
        "original_url": url,
        "original_domain": _base_domain(url),
        "citation_pdf_url": pdf_url,
        "pdf_host_domain": _base_domain(pdf_url),
        "hop2_outcome": hop2["outcome"],
        "hop2_status": hop2["status"],
        "hop2_content_type": hop2["content_type"],
        "hop2_title": hop2["title"],
        "hop2_body_preview": hop2["body_preview"],
        "hop1_outcome": hop1["outcome"],
    }


async def _hop1_extract(client: httpx.AsyncClient, url: str) -> dict:
    rec = {"outcome": None, "citation_pdf_url": None}
    try:
        async with client.stream("GET", url, timeout=HOP_TIMEOUT) as resp:
            if resp.status_code >= 400:
                rec["outcome"] = f"HTTP_{resp.status_code}"
                return rec
            ct = resp.headers.get("content-type", "").lower()
            if "text/html" not in ct:
                rec["outcome"] = f"UNEXPECTED_CT:{ct[:40]}"
                return rec
            body = b""
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                body += chunk
                if len(body) >= HTML_READ_BYTES:
                    break
            body_str = body.decode("utf-8", errors="replace")
            m = CITATION_PDF_META_RE.search(body_str)
            if m:
                rec["citation_pdf_url"] = m.group(1) or m.group(2)
                rec["outcome"] = "OK"
            else:
                rec["outcome"] = "NO_META_TAG"
    except httpx.TimeoutException:
        rec["outcome"] = "TIMEOUT"
    except httpx.RequestError as e:
        rec["outcome"] = f"CONN_ERROR:{type(e).__name__}"
    except Exception as e:
        rec["outcome"] = f"ERROR:{type(e).__name__}"
    return rec


def _base_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


async def _hop2_classify(client: httpx.AsyncClient, pdf_url: str) -> dict:
    rec = {"outcome": None, "status": None, "content_type": None, "title": None, "body_preview": None}
    try:
        async with client.stream("GET", pdf_url, timeout=HOP_TIMEOUT) as resp:
            rec["status"] = resp.status_code
            ct = resp.headers.get("content-type", "").lower()
            rec["content_type"] = ct

            if resp.status_code >= 400:
                rec["outcome"] = f"HTTP_{resp.status_code}"
                return rec

            body = b""
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                body += chunk
                if len(body) >= HTML_READ_BYTES:
                    break

            if "application/pdf" in ct or body[:4] == b"%PDF":
                rec["outcome"] = "PDF_OK"
                return rec

            if "text/html" in ct:
                body_str = body.decode("utf-8", errors="replace")
                title_m = re.search(r"<title[^>]*>([^<]{1,300})</title>", body_str, re.IGNORECASE | re.DOTALL)
                if title_m:
                    rec["title"] = title_m.group(1).strip()[:200]
                visible = re.sub(r"<[^>]+>", " ", body_str[:2000])
                visible = re.sub(r"\s+", " ", visible).strip()
                rec["body_preview"] = visible[:200]
                rec["outcome"] = "HTML_FALLBACK"
                return rec

            rec["outcome"] = "HTML_FALLBACK"
    except httpx.TimeoutException:
        rec["outcome"] = "TIMEOUT"
    except httpx.RequestError as e:
        rec["outcome"] = f"CONN_ERROR:{type(e).__name__}"
    except Exception as e:
        rec["outcome"] = f"ERROR:{type(e).__name__}"
    return rec


if __name__ == "__main__":
    asyncio.run(run_probe())
