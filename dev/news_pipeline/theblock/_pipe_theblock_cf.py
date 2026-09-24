# INFRASTRUCTURE

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests as cffi_requests

CONCURRENCY_CF        = 20
CF_TIMEOUT_S          = 15

TARGET_CF_CHECK       = "https://www.theblock.co/sitemap_tbco_post_type_post_0.xml"
XML_MARKERS           = [b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>"]


# FUNCTIONS

def cf_get(proxy_url: str, url: str) -> tuple[bytes, int]:
    """GET url via proxy with curl_cffi chrome impersonation. Returns (body, status_code)."""
    try:
        s = cffi_requests.Session(impersonate="chrome")
        r = s.get(url, proxies={"http": proxy_url, "https": proxy_url}, timeout=CF_TIMEOUT_S)
        s.close()
        return r.content, r.status_code
    except Exception:
        return b"", 0


def is_xml(body: bytes) -> bool:
    head = body[:500]
    return any(m in head for m in XML_MARKERS)


def stage2_cf_check(proxy_urls: list[str]) -> list[str]:
    """CF-pass check on neutral-alive proxies. Returns list of passing proxy URL strings."""
    passing: list[str] = []
    lock = threading.Lock()
    done = [0]
    total = len(proxy_urls)

    def check_one(purl: str) -> str | None:
        body, status = cf_get(purl, TARGET_CF_CHECK)
        with lock:
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == total:
                sys.stdout.write(f"\r  {done[0]}/{total} checked  ")
                sys.stdout.flush()
        return purl if (status == 200 and is_xml(body)) else None

    with ThreadPoolExecutor(max_workers=CONCURRENCY_CF) as ex:
        futures = {ex.submit(check_one, p): p for p in proxy_urls}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                passing.append(result)
    print()
    return passing
