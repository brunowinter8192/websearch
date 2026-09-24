# INFRASTRUCTURE
import asyncio
import re
import sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx

GLOBAL_MAX_CONNECTIONS = 8
GLOBAL_MAX_KEEPALIVE = 4
DOMAIN_CONCURRENCY_CAP = 2
DOMAIN_COURTESY_SLEEP = 0.5
TIER1_TIMEOUT = 15.0
DEFAULT_TIMEOUT = 8.0
HTML_READ_BYTES = 32 * 1024
PDF_SNIFF_BYTES = 1024

PAYWALL_MARKERS = [
    "institutional login",
    "institutional access",
    "purchase article",
    "buy this article",
    "purchase access",
    "sign in to read",
    "log in to access",
    "access options",
    "get full access",
    "full text is not available",
    "subscribe to read",
    "register to read",
    "article access required",
]


# FUNCTIONS

async def _classify_all(sampled_pool: list[tuple[str, str]]) -> list[dict]:
    limits = httpx.Limits(max_connections=GLOBAL_MAX_CONNECTIONS, max_keepalive_connections=GLOBAL_MAX_KEEPALIVE)
    domain_sems: dict[str, asyncio.Semaphore] = {}
    results: list[dict | None] = [None] * len(sampled_pool)

    async with httpx.AsyncClient(
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; research-probe/1.0)"},
    ) as client:
        tasks = [
            _classify_with_cap(client, url, tier, idx, domain_sems, results)
            for idx, (url, tier) in enumerate(sampled_pool)
        ]
        done = 0
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 50 == 0 or done == total:
                print(f"[classify] {done}/{total}", file=sys.stderr)

    return [r for r in results if r is not None]


async def _classify_with_cap(
    client: httpx.AsyncClient,
    url: str,
    tier: str,
    idx: int,
    domain_sems: dict[str, asyncio.Semaphore],
    results: list,
) -> None:
    netloc = urlparse(url).netloc
    if netloc not in domain_sems:
        domain_sems[netloc] = asyncio.Semaphore(DOMAIN_CONCURRENCY_CAP)
    async with domain_sems[netloc]:
        result = await _classify_url(client, url, tier)
        await asyncio.sleep(DOMAIN_COURTESY_SLEEP)
    results[idx] = result


async def _classify_url(client: httpx.AsyncClient, original_url: str, tier: str) -> dict:
    transformed_url = _apply_transform(original_url)
    fetch_url = transformed_url or original_url
    timeout = TIER1_TIMEOUT if tier == "T1" else DEFAULT_TIMEOUT
    rec = _init_classify_record(original_url, transformed_url, tier)

    try:
        async with client.stream("GET", fetch_url, timeout=timeout) as resp:
            await _classify_response(rec, resp)
    except httpx.TimeoutException:
        rec["outcome"] = "TIMEOUT"
    except httpx.ConnectError as e:
        rec["outcome"] = "CONNECTION_ERROR"
        rec["page_title"] = str(e)[:80]
    except httpx.RequestError as e:
        rec["outcome"] = "CONNECTION_ERROR"
        rec["page_title"] = str(e)[:80]
    except Exception as e:
        rec["outcome"] = "CONNECTION_ERROR"
        rec["page_title"] = f"{type(e).__name__}: {str(e)[:60]}"

    return rec


def _init_classify_record(original_url: str, transformed_url: str | None, tier: str) -> dict:
    return {
        "original_url": original_url,
        "transformed_url": transformed_url,
        "tier": tier,
        "final_url": None,
        "outcome": None,
        "status_code": None,
        "content_type": None,
        "page_title": None,
        "has_citation_pdf_url": False,
        "paywall_marker": None,
        "citation_pdf_url": None,
    }


async def _classify_response(rec: dict, resp: httpx.Response) -> None:
    rec["status_code"] = resp.status_code
    rec["final_url"] = str(resp.url)
    ct = resp.headers.get("content-type", "").lower()
    rec["content_type"] = ct

    if resp.status_code >= 400:
        rec["outcome"] = f"HTTP_{resp.status_code}"
        return

    body = await _read_response_body(resp)

    if "application/pdf" in ct or body[:4] == b"%PDF":
        rec["outcome"] = "PDF_OK"
        return

    if "text/html" in ct:
        _classify_html_body(rec, body)
        return

    rec["outcome"] = "HTML_OK"


async def _read_response_body(resp: httpx.Response) -> bytes:
    body_chunks: list[bytes] = []
    bytes_read = 0
    async for chunk in resp.aiter_bytes(chunk_size=4096):
        body_chunks.append(chunk)
        bytes_read += len(chunk)
        if bytes_read >= HTML_READ_BYTES:
            break
    return b"".join(body_chunks)


def _classify_html_body(rec: dict, body: bytes) -> None:
    try:
        body_str = body.decode("utf-8", errors="replace")
    except Exception:
        body_str = ""

    rec["page_title"] = _extract_title(body_str)

    m = re.search(
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        body_str, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
            body_str, re.IGNORECASE,
        )
    if m:
        rec["has_citation_pdf_url"] = True
        rec["citation_pdf_url"] = m.group(1)[:200]

    body_lower = body_str.lower()
    for marker in PAYWALL_MARKERS:
        if marker in body_lower:
            rec["paywall_marker"] = marker
            break

    if rec["has_citation_pdf_url"]:
        rec["outcome"] = "HTML_HAS_PDF_LINK"
    elif rec["paywall_marker"]:
        rec["outcome"] = "HTML_PAYWALL"
    else:
        rec["outcome"] = "HTML_OK"


def _apply_transform(url: str) -> str | None:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    if domain == "arxiv.org":
        path = parsed.path
        if re.match(r"^/(abs|html)/", path):
            new_path = re.sub(r"^/(abs|html)/", "/pdf/", path)
            return urlunparse(parsed._replace(path=new_path))
        return None

    if domain == "aclanthology.org":
        path = parsed.path
        if path.lower().endswith(".pdf"):
            return None
        new_path = path.rstrip("/") + ".pdf"
        return urlunparse(parsed._replace(path=new_path))

    if domain == "openreview.net":
        if parsed.path == "/forum":
            return urlunparse(parsed._replace(path="/pdf"))
        return None

    return None


def _extract_title(body: str) -> str | None:
    m = re.search(r"<title[^>]*>([^<]{1,300})</title>", body, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return None
