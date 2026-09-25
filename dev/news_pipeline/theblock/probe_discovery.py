#!/usr/bin/env python3
# INFRASTRUCTURE
import subprocess
import re
import time
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _probe_discovery_report import build_report, post_id, url_type

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BASE = "https://www.theblock.co"
CACHE_DIR   = Path("dev/news_pipeline/theblock/cache")
NEWS_CACHE  = CACHE_DIR / "news_sitemap.json"
REPORT_PATH = "dev/news_pipeline/theblock/discover_coverage_report.md"

SUB_DELAY    = 5.0
BACKOFF_WAIT = [60, 120, 180]
MAX_RETRIES  = 3

RSS_PREPROBE_URLS = [
    "https://www.theblock.co/post/403982/solana-infrastructure-firm-helius-acquires-light-protocol-expand-onchain-privacy",
    "https://www.theblock.co/post/404144/curve-launches-llamalend-v2-first-optimism-supported-250000-op-token-grant",
    "https://www.theblock.co/post/404185/ethereum-fully-zero-knowledge-proof-based-protocol-3-to-5-years-joe-lubin",
    "https://www.theblock.co/post/404216/bitcoin-layer-2-botanix-to-wind-down-network-urges-users-to-withdraw-assets",
    "https://www.theblock.co/post/404223/new-york-regulator-proposes-stablecoin-rule-to-align-with-federal-genius-act-adds-reserve-limits",
    "https://www.theblock.co/post/404229/more-than-half-bitcoin-supply-underwater-bottom-after-final-leg-lower-k33",
    "https://www.theblock.co/post/404237/in-the-shadow-of-geopolitics-and-ai-bitcoin-hovers-near-cycle-lows-as-etf-outflows-and-rate-fears-deepen-worst-stretch-of-2026",
    "https://www.theblock.co/post/404238/pyth-launches-24-7-proprietary-indices-for-us-equities-oil-and-metals",
    "https://www.theblock.co/post/404243/ripple-launches-toolkit-for-agentic-payments-on-xrpl",
    "https://www.theblock.co/post/404255/benchmark-securitize-positive-outlier-sets-16-target-nyse-listing-nears",
    "https://www.theblock.co/post/404258/cftc-unveils-sweeping-rule-proposal-fast-growing-prediction-markets",
    "https://www.theblock.co/post/404272/fold-discloses-45-million-bitcoin-sale-pays-off-collateralized-debt-in-full-shares-surge-160",
    "https://www.theblock.co/post/404273/uk-crypto-advocates-push-back-exchange-transfer-blocks-banks-choking-off-adoption",
    "https://www.theblock.co/post/404281/megaeth-mnx-pre-seed-funding-valuation-ai-focused-futures-exchange",
    "https://www.theblock.co/post/404288/mastercard-agent-pay-machines-support-autonomous-ai-transactions-stablecoins",
    "https://www.theblock.co/post/404303/tether-leads-up-to-1-4-billion-round-in-robotics-firm-neura-plans-crypto-wallet-integration",
    "https://www.theblock.co/post/404304/raydium-dex-1-34-million-exploit-retired-amm-program-treasury-cover-losses",
    "https://www.theblock.co/post/404316/cryptoquant-sees-bitcoin-bottom-near-53600-while-demand-remains-deeply-unfavorable",
    "https://www.theblock.co/post/404324/elon-musks-spacex-ipo-could-become-bitcoins-latest-headwind",
    "https://www.theblock.co/post/404341/bitcoin-stablecoins-tokenization-bitwise-cio-financial-advisors",
]


# ORCHESTRATOR

def probe_discovery_workflow():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print("=== theblock.co discovery coverage probe ===")

    print("\n[1/4] Full sitemap union (per-sub checkpoint) ...")
    sitemap_urls, sub_stats = fetch_full_sitemap_union()

    print("\n[2/4] News sitemap ...")
    news_urls, news_from_cache = fetch_news_sitemap()

    print("\n[3/4] RSS ...")
    rss_urls, rss_rate_limited = fetch_rss()

    print("\n[4/4] Bounded UI crawl ...")
    ui_urls, ui_status = fetch_ui_crawl()

    print("\n[5/5] Building report ...")
    report = build_report(sitemap_urls, sub_stats, news_urls, news_from_cache,
                          rss_urls, rss_rate_limited, ui_urls, ui_status)
    write_report(report)

    total   = sub_stats["sub_count"]
    fetched = sub_stats["fetched"]
    remain  = sub_stats["remaining"]
    status  = "COMPLETE" if remain == 0 else f"PARTIAL ({remain} subs pending — re-run to resume)"
    print(f"\nReport written: {REPORT_PATH}")
    print(f"Sitemap: {fetched}/{total} subs fetched — {status}")


# FUNCTIONS

def fetch_full_sitemap_union():
    index_xml = curl_get(f"{BASE}/sitemap_tbco_index.xml")
    sub_urls = extract_locs(index_xml)

    if not sub_urls:
        sub_urls = _reconstruct_sub_urls_from_cache()
        if sub_urls:
            print(f"  index CF-blocked — reconstructed {len(sub_urls)} sub URLs from cache dir")
        else:
            print("  index CF-blocked, no cache — aborting sitemap fetch")
            return [], {"sub_count": 0, "fetched": 0, "remaining": 0, "blocked_subs": []}

    print(f"  index sitemap: {len(sub_urls)} sub-sitemaps")

    cached_subs  = [u for u in sub_urls if load_sub_cache(u) is not None]
    to_fetch     = [u for u in sub_urls if load_sub_cache(u) is None]
    print(f"  cached: {len(cached_subs)}, to fetch: {len(to_fetch)}")

    blocked_subs = _fetch_pending_subs(to_fetch)

    all_urls_set, fetched_count = _aggregate_cached_subs(sub_urls)

    remaining = len(sub_urls) - fetched_count
    print(f"  unique URLs confirmed: {len(all_urls_set):,} from {fetched_count}/{len(sub_urls)} subs")

    return list(all_urls_set), {
        "sub_count":   len(sub_urls),
        "fetched":     fetched_count,
        "remaining":   remaining,
        "blocked_subs": blocked_subs,
    }


def fetch_news_sitemap():
    xml = curl_get(f"{BASE}/sitemap_tbco_news.xml")
    if not is_cf_blocked(xml):
        locs = [normalize_url(u) for u in extract_locs(xml)]
        unique = list(set(locs))
        if unique:
            print(f"  news sitemap: {len(unique)} unique URLs")
            NEWS_CACHE.write_text(json.dumps({"urls": unique}))
            return unique, False

    if NEWS_CACHE.exists():
        cached = json.loads(NEWS_CACHE.read_text())
        if cached.get("urls"):
            print(f"  news sitemap: CF-blocked — cache: {len(cached['urls'])} URLs")
            return cached["urls"], True

    print("  news sitemap: CF-blocked, no cache")
    return [], True


def fetch_rss():
    xml = curl_get(f"{BASE}/rss.xml")
    if is_cf_blocked(xml):
        print(f"  RSS: HTTP 429 — pre-probe sample ({len(RSS_PREPROBE_URLS)} URLs)")
        return list(RSS_PREPROBE_URLS), True
    links = re.findall(r'<link>\s*(https?://[^<\s]+)\s*</link>', xml)
    guids = re.findall(r'<guid[^>]*>\s*(https?://[^<\s]+)\s*</guid>', xml)
    articles = [normalize_url(u) for u in links + guids
                if 'theblock.co' in u and re.search(r'/post/|/linked/', u)]
    unique = list(set(articles))
    print(f"  RSS: {len(unique)} unique article URLs ({len(links + guids)} <link>/<guid> tags)")
    return unique, False


def fetch_ui_crawl():
    status_notes = []
    all_post_urls = set()
    pages_fetched = 0

    for path in ["/latest", "/latest-crypto-news"]:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-H", f"User-Agent: {UA}", f"{BASE}{path}"],
            capture_output=True, text=True
        )
        code = r.stdout.strip()
        note = f"{path} → HTTP {code}"
        if code == "429":
            note += " (Cloudflare rate-limit)"
        elif path == "/latest" and code in ("301", "302"):
            note += " (redirect to /latest-crypto-news)"
        status_notes.append(note)

    latest_news_ok = any("latest-crypto-news → HTTP 200" in n for n in status_notes)

    for cat in ["/category/markets", "/category/defi", "/category/bitcoin"]:
        time.sleep(2.0)
        html = curl_get(f"{BASE}{cat}")
        hrefs = re.findall(r'href="(/post/\d+/[^"]+)"', html)
        urls = {normalize_url(BASE + h) for h in hrefs}
        all_post_urls.update(urls)
        print(f"  {cat}: {len(urls)} /post/ hrefs in raw HTML")
        pages_fetched += 1
        if len(all_post_urls) >= 300:
            break

    if latest_news_ok and len(all_post_urls) < 300:
        time.sleep(2.0)
        html = curl_get(f"{BASE}/latest-crypto-news")
        hrefs = re.findall(r'href="(/post/\d+/[^"]+)"', html)
        urls = {normalize_url(BASE + h) for h in hrefs}
        all_post_urls.update(urls)
        print(f"  /latest-crypto-news: {len(urls)} /post/ hrefs in raw HTML")
        pages_fetched += 1

    unique = list(all_post_urls)
    print(f"  UI total: {len(unique)} unique /post/ URLs across {pages_fetched} pages")
    return unique, status_notes


def write_report(content):
    with open(REPORT_PATH, "w") as f:
        f.write(content)


def _reconstruct_sub_urls_from_cache():
    sub_urls = []
    for f in sorted(CACHE_DIR.glob("sub_*.json")):
        d = json.loads(f.read_text())
        if d.get("sub"):
            sub_urls.append(d["sub"])
    return sub_urls


def _fetch_pending_subs(to_fetch):
    blocked_subs = []
    for i, sub_url in enumerate(to_fetch, 1):
        sys.stdout.write(f"\r  [{i}/{len(to_fetch)}] {sub_url.split('/')[-1][:55]}   ")
        sys.stdout.flush()
        time.sleep(SUB_DELAY)
        urls, status = fetch_sub_with_retry(sub_url)
        if status == "ok":
            save_sub_cache(sub_url, urls)
        else:
            blocked_subs.append(sub_url)
            print(f"\n  FAILED (max retries): {sub_url.split('/')[-1]}")

    if to_fetch:
        print()
    return blocked_subs


def _aggregate_cached_subs(sub_urls):
    all_urls_set = set()
    fetched_count = 0
    for sub_url in sub_urls:
        cached = load_sub_cache(sub_url)
        if cached is not None:
            all_urls_set.update(cached)
            fetched_count += 1
    return all_urls_set, fetched_count


def load_sub_cache(sub_url):
    p = sub_cache_path(sub_url)
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return d.get("urls", [])


def fetch_sub_with_retry(sub_url):
    for attempt, wait_secs in enumerate([0] + BACKOFF_WAIT):
        if wait_secs:
            print(f"\n    CF 429 — waiting {wait_secs}s (retry {attempt}/{MAX_RETRIES}) ...")
            time.sleep(wait_secs)
        xml = curl_get(sub_url)
        if not is_cf_blocked(xml):
            locs = [normalize_url(u) for u in extract_locs(xml)]
            return locs, "ok"
        if attempt == MAX_RETRIES:
            return None, "cf_blocked"
    return None, "cf_blocked"


def save_sub_cache(sub_url, urls):
    p = sub_cache_path(sub_url)
    p.write_text(json.dumps({"sub": sub_url, "url_count": len(urls), "urls": urls}))


def curl_get(url, delay=0.0):
    if delay:
        time.sleep(delay)
    result = subprocess.run(
        ["curl", "-s", "-L", "--max-time", "20",
         "-H", f"User-Agent: {UA}",
         "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "-H", "Accept-Language: en-US,en;q=0.5",
         url],
        capture_output=True, text=True
    )
    return result.stdout


def extract_locs(xml_text):
    return re.findall(r'<loc>\s*(https?://[^<\s]+)\s*</loc>', xml_text)


def is_cf_blocked(text):
    return '<Code>429</Code>' in text or '<Code>403</Code>' in text


def normalize_url(url):
    url = re.sub(r'\?.*', '', url)
    return url.rstrip('/')


def sub_cache_path(sub_url):
    name = sub_url.split('/')[-1].replace('.xml', '')
    return CACHE_DIR / f"sub_{name}.json"


if __name__ == "__main__":
    probe_discovery_workflow()
