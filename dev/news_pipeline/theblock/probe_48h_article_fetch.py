# INFRASTRUCTURE
import argparse
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "acquire_pipe"))

from curated_sources import load_backfill_pool
from p1_fetch import fetch_url, XML_MARKERS

INDEX_URL      = "https://www.theblock.co/sitemap_tbco_index.xml"
OUTPUT_DIR     = Path(__file__).parent / "probe_48h_output"
DIRECT_TIMEOUT = 15.0
RACE_WIDTH     = 128

_INDEX_LOC_RE = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_URL_BLOCK_RE = re.compile(rb"<url>(.*?)</url>", re.DOTALL)
_LOC_RE       = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_MOD_RE       = re.compile(rb"<lastmod>([^<]+)</lastmod>")
_NUM_RE       = re.compile(r"_(\d+)\.xml$")


# ORCHESTRATOR

def probe_48h_article_fetch_workflow(hours: float) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    print("[probe] Loading backfill pool...")
    pool = load_backfill_pool()
    print(f"[probe] Pool: {len(pool)} proxies")

    print("[probe] Fetching sitemap index...")
    post_subs = _fetch_index(pool)
    if not post_subs:
        raise RuntimeError("No post_type_post sub-sitemaps found in index")
    print(f"[probe] post_type_post sub-sitemaps in index: {len(post_subs)}")

    sub_url = _pick_highest_numbered(post_subs)
    print(f"[probe] Selected (highest-numbered): {sub_url.split('/')[-1]}")

    print("[probe] Fetching sub-sitemap...")
    ok, content = _fetch_parallel(sub_url, pool, "xml")
    if not ok:
        raise RuntimeError(f"Sub-sitemap fetch failed: {sub_url}")

    entries = _parse_url_blocks(content)
    print(f"[probe] Entries in sub-sitemap: {len(entries)}")

    recent = [(u, m) for u, m in entries if m >= cutoff]
    print(f"[probe] Entries in {hours:.0f}h window: {len(recent)}")

    if len(recent) >= 2:
        targets = recent[:2]
        print(f"[probe] Using 2 entries from {hours:.0f}h window")
    else:
        by_date = sorted(entries, key=lambda x: x[1], reverse=True)
        targets = by_date[:2]
        print(f"[probe] <2 in {hours:.0f}h window — using 2 newest entries from sub-sitemap")

    if not targets:
        print("[probe] Sub-sitemap appears empty — nothing to fetch")
        return

    for idx, (url, mod) in enumerate(targets):
        print(f"[probe] Fetching article {idx + 1}: {url}")
        ok, content = _fetch_parallel(url, pool, "html")
        if ok:
            out_path = OUTPUT_DIR / f"article_{idx}.html"
            out_path.write_bytes(content)
            print(f"  → OK, {len(content):,} bytes → {out_path.name}")
        else:
            print(f"  → FAILED (all {RACE_WIDTH} parallel proxies missed)")


# FUNCTIONS

def _fetch_index(pool: list) -> list[str]:
    content = _fetch_index_direct()
    if content is None:
        ok, content = _fetch_parallel(INDEX_URL, pool, "xml")
        if not ok:
            raise RuntimeError("Index fetch failed (direct + parallel both failed)")
    locs = _INDEX_LOC_RE.findall(content)
    return [u.decode().strip() for u in locs if b"post_type_post" in u]


def _pick_highest_numbered(urls: list[str]) -> str:
    def _num(u: str) -> int:
        m = _NUM_RE.search(u)
        return int(m.group(1)) if m else -1
    return max(urls, key=_num)


def _parse_url_blocks(content: bytes) -> list[tuple[str, datetime]]:
    results: list[tuple[str, datetime]] = []
    for block in _URL_BLOCK_RE.finditer(content):
        body  = block.group(1)
        loc_m = _LOC_RE.search(body)
        mod_m = _MOD_RE.search(body)
        if not loc_m or not mod_m:
            continue
        url     = loc_m.group(1).decode().strip()
        mod_raw = mod_m.group(1).decode().strip().replace("Z", "+00:00")
        mod = datetime.fromisoformat(mod_raw)
        if mod.tzinfo is None:
            mod = mod.replace(tzinfo=timezone.utc)
        results.append((url, mod))
    return results


def _fetch_parallel(
    url: str, pool: list, content_type: str, n: int = RACE_WIDTH
) -> tuple[bool, bytes]:
    candidates = pool[:]
    random.shuffle(candidates)
    total = (len(candidates) + n - 1) // n
    for wi, start in enumerate(range(0, len(candidates), n), 1):
        wave = candidates[start:start + n]
        ex   = ThreadPoolExecutor(max_workers=len(wave))
        futs = {ex.submit(fetch_url, p, hp, url, content_type): (p, hp) for p, hp in wave}
        try:
            for fut in as_completed(futs):
                ok, content = fut.result()
                if ok:
                    return True, content
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        print(f"[probe]   wave {wi}/{total} all missed, next...")
    return False, b""


def _fetch_index_direct() -> bytes | None:
    r = httpx.get(INDEX_URL, timeout=DIRECT_TIMEOUT, follow_redirects=True)
    head = r.content[:500]
    if r.status_code == 200 and any(m in head for m in XML_MARKERS):
        print(f"[sitemap] Direct OK ({len(r.content):,} bytes)")
        return r.content
    print(f"[sitemap] Direct: status={r.status_code}, no XML marker — parallel fallback")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="48h article delta probe: theblock.co highest post-sitemap → parallel race fetch → raw HTML"
    )
    parser.add_argument(
        "--hours", type=float, default=48.0,
        help="Lookback window in hours; <2 hits → fallback to 2 newest (default: 48)",
    )
    args = parser.parse_args()
    probe_48h_article_fetch_workflow(hours=args.hours)
