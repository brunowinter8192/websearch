# INFRASTRUCTURE
import sys
import re
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url, THEBLOCK_INDEX, XML_MARKERS
from p2_cooldown import PersistentCooldownManager

DIRECT_TIMEOUT = 15.0
_LOC_RE        = re.compile(rb"<loc>(https?://[^<]+)</loc>")


# FUNCTIONS

def build_sitemap_target(pool: list | None = None) -> list[str]:
    content = _fetch_index_direct()
    if content is None:
        content = _compute_content(content, pool)
    return _parse_loc_urls(content)


def _fetch_index_direct() -> bytes | None:
    r = httpx.get(THEBLOCK_INDEX, timeout=DIRECT_TIMEOUT, follow_redirects=True)
    head = r.content[:500]
    if r.status_code == 200 and any(m in head for m in XML_MARKERS):
        print(f"[sitemap] Direct fetch OK ({len(r.content):,} bytes)")
        return r.content
    print(f"[sitemap] Direct fetch: status={r.status_code}, no XML marker — proxy fallback")
    return None


def _compute_content(content, pool):
    content = _fetch_index_via_proxy(pool if pool is not None else [])
    return content


def _parse_loc_urls(content: bytes) -> list[str]:
    return [m.group(1).decode().strip() for m in _LOC_RE.finditer(content)]


def _fetch_index_via_proxy(pool: list) -> bytes:
    cm   = PersistentCooldownManager()
    candidates = cm.eligible_candidates(pool)
    print(f"[sitemap] Proxy fallback: {len(candidates)} candidates")
    for proto, hp in candidates:
        status, content = fetch_url(proto, hp, THEBLOCK_INDEX, "xml")
        if status == "ok":
            print(f"[sitemap] Proxy OK via {proto}://{hp} ({len(content):,} bytes)")
            return content
        if status == "fail":
            cm.mark_burned(proto, hp)
    raise RuntimeError("sitemap index fetch failed: all proxy candidates exhausted")
