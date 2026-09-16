"""
__NEXT_DATA__ agentic discovery probe for docs.github.com/de/rest.

Strategy:
  1. Fetch seed page HTML via curl (no browser needed — __NEXT_DATA__ is in initial HTML).
  2. Parse sidebarTree from __NEXT_DATA__.props.pageProps.mainContext.sidebarTree.
  3. Collect allVersions to discover GHEC/GHES variant URLs.
  4. Fetch GHEC REST page, parse its sidebarTree → additional enterprise-only pages.
  5. Union all found URLs, save discovered set, score vs goldstandard.

Generic vs site-specific markers are logged inline.

Usage:
    ./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py
    ./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py --gold dev/explore_pipeline/goldstandard/docs_github_rest.txt
    ./venv/bin/python dev/explore_pipeline/06_nextdata_probe.py --no-ghec
"""

# INFRASTRUCTURE
import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SEED_URL = "https://docs.github.com/de/rest"
BASE = "https://docs.github.com"
GOLD_DEFAULT = Path(__file__).parent / "goldstandard" / "docs_github_rest.txt"
OUTPUT_DIR = Path(__file__).parent / "md"
DISCOVERED_FILE = Path(__file__).parent / "txt" / "06_discovered_urls.txt"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ORCHESTRATOR

def nextdata_discovery_workflow(gold_path: Path, include_ghec: bool, include_ghes: bool) -> dict:
    log = []
    t0 = time.time()

    blob = fetch_root_nextdata(log)
    if blob is None:
        return {"log": log, "urls": []}

    mc, fpt_rest, cats_fpt = parse_fpt_sidebar(log, blob)
    all_versions = detect_versions(log, mc)
    ghec_rest = fetch_ghec_sidebar(log, include_ghec, all_versions, cats_fpt)
    ghec_normalized = normalize_ghec_urls(log, ghec_rest, fpt_rest)
    ghes_rest, ghes_normalized = fetch_ghes_sidebars(log, include_ghes, all_versions, fpt_rest, ghec_normalized)
    all_normalized, all_raw, all_urls = union_discovered_urls(
        log, fpt_rest, ghec_rest, ghec_normalized, ghes_rest, ghes_normalized)
    save_discovered_urls(log, all_urls)
    gold, recall, elapsed_total = score_against_gold(log, gold_path, all_urls, t0)
    report_path = save_full_report(
        log, recall, gold, elapsed_total, fpt_rest, ghec_rest, ghes_rest, ghec_normalized, all_normalized)

    return {"log": log, "recall": recall, "report_path": report_path}


# FUNCTIONS

# Step 1: fetch root __NEXT_DATA__ (GENERIC — works for any Next.js site)
def fetch_root_nextdata(log: list) -> dict | None:
    log.append("## Step 1: __NEXT_DATA__ from seed page")
    log.append("Generic move: Next.js embeds full nav tree in initial HTML — no browser needed.")
    t1 = time.time()
    html = fetch_html(SEED_URL)
    blob = extract_nextdata(html)
    elapsed_fetch = time.time() - t1
    if not blob:
        log.append("FAIL: no __NEXT_DATA__ found — site may not be Next.js SSR.")
        return None
    log.append(f"Found __NEXT_DATA__: {len(json.dumps(blob))} chars  ({elapsed_fetch:.1f}s)")
    return blob


# Step 2: parse FPT sidebar (GENERIC — walk sidebarTree recursively)
def parse_fpt_sidebar(log: list, blob: dict) -> tuple[dict, list, dict]:
    log.append("\n## Step 2: parse sidebarTree (free-pro-team@latest)")
    log.append("Generic move: sidebarTree in mainContext contains full product nav.")
    mc = blob["props"]["pageProps"]["mainContext"]
    fpt_urls = collect_hrefs(mc["sidebarTree"], BASE)
    fpt_rest = [u for u in fpt_urls if "/rest" in urlparse(u).path]
    log.append(f"FPT sidebarTree: {len(fpt_rest)} URLs matching /rest")
    cats_fpt = count_categories(fpt_rest, "/de/rest/")
    log.append(f"FPT categories: {len(cats_fpt)}")
    return mc, fpt_rest, cats_fpt


# Step 3: detect available versions (GENERIC — allVersions in mainContext)
def detect_versions(log: list, mc: dict) -> dict:
    log.append("\n## Step 3: detect versions via allVersions")
    log.append("Generic move: allVersions lists all content variants — check each for extra nav entries.")
    all_versions = mc.get("allVersions", {})
    log.append(f"Versions found: {list(all_versions.keys())}")
    return all_versions


# Step 4: fetch GHEC sidebar (SITE-SPECIFIC: knowing GHEC has enterprise-admin etc.)
# Generic framing: for each version, construct version-prefixed URL and compare nav.
def fetch_ghec_sidebar(log: list, include_ghec: bool, all_versions: dict, cats_fpt: dict) -> list:
    ghec_rest = []
    if include_ghec and "enterprise-cloud@latest" in all_versions:
        log.append("\n## Step 4: GHEC sidebarTree (enterprise-cloud@latest)")
        log.append("Partially generic: for any versioned doc site, fetch each version's nav and union.")
        log.append("Site-specific: knowing that enterprise-cloud prefix is /de/enterprise-cloud@latest/.")
        ghec_url = f"{BASE}/de/enterprise-cloud@latest/rest"
        t2 = time.time()
        html_ghec = fetch_html(ghec_url)
        blob_ghec = extract_nextdata(html_ghec)
        elapsed_ghec = time.time() - t2
        if blob_ghec:
            mc_ghec = blob_ghec["props"]["pageProps"]["mainContext"]
            ghec_urls_all = collect_hrefs(mc_ghec["sidebarTree"], BASE)
            ghec_rest = [u for u in ghec_urls_all if "/rest" in urlparse(u).path]
            cats_ghec = count_categories(ghec_rest, "/de/enterprise-cloud@latest/rest/")
            log.append(f"GHEC sidebarTree: {len(ghec_rest)} URLs  ({elapsed_ghec:.1f}s)")
            log.append(f"GHEC categories: {len(cats_ghec)}")
            # GHEC-only categories (not in FPT path space — they're at enterprise-cloud prefix)
            fpt_cats = set(cats_fpt.keys())
            ghec_cats = set(cats_ghec.keys())
            ghec_only = ghec_cats - fpt_cats
            log.append(f"GHEC-only categories: {sorted(ghec_only)}")
        else:
            log.append("WARN: no __NEXT_DATA__ on GHEC page")
    return ghec_rest


# Step 4b: normalize GHEC URLs to canonical /de/rest/... form
# Key insight: goldstandard uses /de/rest/enterprise-admin/... (pre-redirect form),
# not /de/enterprise-cloud@latest/rest/enterprise-admin/... (post-redirect).
# Generic move: strip version prefix to get canonical short-form URL.
def normalize_ghec_urls(log: list, ghec_rest: list, fpt_rest: list) -> list:
    ghec_normalized = []
    if ghec_rest:
        for u in ghec_rest:
            normalized = u.replace("/de/enterprise-cloud@latest/rest/", "/de/rest/")
            ghec_normalized.append(normalized)
        log.append(f"GHEC normalized to /de/rest/: {len(ghec_normalized)} URLs")
        ghec_only_normalized = set(ghec_normalized) - set(fpt_rest)
        log.append(f"GHEC-only pages (not in FPT): {len(ghec_only_normalized)}")
    return ghec_normalized


# Step 5: GHES sidebars — ALL versions (generic: check every version listed in allVersions)
# Key insight: deprecated pages disappear from newer versions but persist in older ones.
# Generic move: iterate ALL versions, union their normalized sidebars.
def fetch_ghes_sidebars(log: list, include_ghes: bool, all_versions: dict,
                        fpt_rest: list, ghec_normalized: list) -> tuple[list, list]:
    ghes_rest = []
    ghes_normalized_set: set = set()
    if include_ghes:
        log.append("\n## Step 5: GHES sidebarTree — all versions")
        log.append("Generic move: deprecated pages disappear from newer versions but persist in older.")
        log.append("Check every version listed in allVersions, union normalized results.")
        ghes_versions = [v for v in all_versions if v.startswith("enterprise-server@")]
        log.append(f"GHES versions to check: {ghes_versions}")
        t3 = time.time()
        cumulative_new = 0
        for ver in ghes_versions:
            ver_url = f"{BASE}/de/{ver}/rest"
            try:
                html_v = fetch_html(ver_url)
                blob_v = extract_nextdata(html_v)
                if not blob_v:
                    log.append(f"  {ver}: no __NEXT_DATA__")
                    continue
                mc_v = blob_v["props"]["pageProps"]["mainContext"]
                ver_raw = collect_hrefs(mc_v["sidebarTree"], BASE)
                ver_rest = [u for u in ver_raw if "/rest" in urlparse(u).path]
                # Normalize: strip version-specific prefix
                ver_normalized = {u.replace(f"/de/{ver}/rest/", "/de/rest/") for u in ver_rest}
                net_new = ver_normalized - ghes_normalized_set - set(fpt_rest) - set(ghec_normalized)
                ghes_normalized_set |= ver_normalized
                cumulative_new += len(net_new)
                log.append(f"  {ver}: {len(ver_rest)} raw → {len(ver_normalized)} normalized, "
                           f"{len(net_new)} net new vs prior")
                ghes_rest.extend(ver_rest)
            except Exception as exc:
                log.append(f"  {ver}: WARN — {exc}")
        elapsed_ghes = time.time() - t3
        ghes_normalized = list(ghes_normalized_set)
        ghes_only = ghes_normalized_set - set(fpt_rest) - set(ghec_normalized)
        log.append(f"GHES union: {len(ghes_normalized_set)} normalized, {len(ghes_only)} net new vs FPT+GHEC "
                   f"({elapsed_ghes:.1f}s)")
    return ghes_rest, ghes_normalized


# Step 6: union all discovered URLs (all normalized to /de/rest/... form)
def union_discovered_urls(log: list, fpt_rest: list, ghec_rest: list, ghec_normalized: list,
                          ghes_rest: list, ghes_normalized: list) -> tuple[list, list, list]:
    log.append("\n## Step 6: union discovered URLs (all normalized to /de/rest/...)")
    log.append("Generic move: strip version prefix to collapse all variant URLs to canonical form.")
    all_normalized = sorted(set(fpt_rest) | set(ghec_normalized) | set(ghes_normalized))
    # Also keep raw (un-normalized) as reference
    all_raw = sorted(set(fpt_rest) | set(ghec_rest) | set(ghes_rest))
    all_urls = all_normalized
    log.append(f"Union normalized: {len(all_normalized)} unique /de/rest/... URLs")
    log.append(f"  FPT raw: {len(fpt_rest)}")
    log.append(f"  GHEC raw: {len(ghec_rest)}  →  normalized unique additions: {len(set(ghec_normalized) - set(fpt_rest))}")
    log.append(f"  GHES (all versions) raw: {len(ghes_rest)}  →  "
               f"normalized unique additions: {len(set(ghes_normalized) - set(fpt_rest) - set(ghec_normalized))}")
    return all_normalized, all_raw, all_urls


# Step 7: save discovered set
def save_discovered_urls(log: list, all_urls: list) -> None:
    save_discovered(all_urls)
    log.append(f"Discovered URLs saved to: {DISCOVERED_FILE}")


# Step 8: score vs goldstandard
def score_against_gold(log: list, gold_path: Path, all_urls: list, t0: float) -> tuple[frozenset, dict, float]:
    log.append("\n## Step 8: recall vs goldstandard")
    gold = load_gold(gold_path)
    recall = compute_recall(all_urls, gold)
    elapsed_total = time.time() - t0
    log.append(f"Gold: {len(gold)} URLs from {gold_path.name}")
    log.append(f"Matched: {recall['matched']} / {len(gold)}  ({recall['recall_pct']:.1f}%)")
    log.append(f"Missing: {recall['missing']}")
    log.append(f"Noise (extra): {recall['noise']}")
    log.append(f"Total wall-clock: {elapsed_total:.1f}s")

    if recall["missing_urls"]:
        log.append(f"\nMissing sample (up to 30):")
        for u in sorted(recall["missing_urls"])[:30]:
            log.append(f"  - {u}")

    if recall["noise_urls"]:
        log.append(f"\nNoise sample (up to 20):")
        for u in sorted(recall["noise_urls"])[:20]:
            log.append(f"  - {u}")

    return gold, recall, elapsed_total


# Step 9: save report
def save_full_report(log: list, recall: dict, gold: frozenset, elapsed_total: float,
                     fpt_rest: list, ghec_rest: list, ghes_rest: list,
                     ghec_normalized: list, all_normalized: list) -> Path:
    report = build_report(log, recall, gold, elapsed_total, len(fpt_rest), len(ghec_rest), len(ghes_rest),
                          len(set(ghec_normalized) - set(fpt_rest)),
                          len(all_normalized))
    report_path = save_report(report)
    log.append(f"\nReport: {report_path}")
    return report_path


# Fetch HTML via urllib (no browser — generic for any HTTP site)
def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


# Extract __NEXT_DATA__ JSON blob from HTML (generic for Next.js SSR pages)
def extract_nextdata(html: str) -> dict | None:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html, re.S
    )
    if not m:
        return None
    return json.loads(m.group(1))


# Recursively collect all hrefs from a sidebar/nav tree node
def collect_hrefs(node: dict, base: str, acc: list | None = None) -> list:
    if acc is None:
        acc = []
    href = node.get("href", "")
    if href and href.startswith("/"):
        acc.append(base + href)
    for child in node.get("childPages", []):
        collect_hrefs(child, base, acc)
    return acc


# Count pages per top-level category, given a URL prefix to strip
def count_categories(urls: list, prefix: str) -> dict:
    cats: dict = {}
    for u in urls:
        stripped = u.replace(f"https://docs.github.com{prefix}", "")
        cat = stripped.split("/")[0] if stripped else "?"
        cats[cat] = cats.get(cat, 0) + 1
    return cats


# Load gold standard, normalize URLs
def load_gold(path: Path) -> frozenset:
    with open(path, encoding="utf-8") as f:
        return frozenset(ln.strip() for ln in f if ln.strip())


# Compute recall metrics
def compute_recall(found_urls: list, gold: frozenset) -> dict:
    found_set = set(found_urls)
    matched = found_set & gold
    missing = gold - found_set
    noise = found_set - gold
    recall_pct = len(matched) / len(gold) * 100 if gold else 0.0
    return {
        "found": len(found_set),
        "matched": len(matched),
        "missing": len(missing),
        "noise": len(noise),
        "recall_pct": recall_pct,
        "missing_urls": missing,
        "noise_urls": noise,
    }


# Save discovered URL list
def save_discovered(urls: list) -> None:
    DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERED_FILE.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")


# Build markdown report
def build_report(log: list, recall: dict, gold: frozenset,
                 elapsed: float, n_fpt: int, n_ghec: int, n_ghes: int,
                 n_ghec_only: int = 0, n_total: int = 0) -> str:
    lines = [
        "# __NEXT_DATA__ Discovery — docs.github.com/de/rest",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Method: __NEXT_DATA__ nav-tree extraction (no browser, pure HTTP fetch)",
        "",
        "## Recall",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Found (normalized union) | {n_total or recall['found']} |",
        f"| FPT sidebar (raw) | {n_fpt} |",
        f"| GHEC sidebar (raw) | {n_ghec} → {n_ghec_only} net additions after normalize |",
        f"| GHES sidebar (raw) | {n_ghes} |",
        f"| Matched gold | {recall['matched']} / {len(gold)} |",
        f"| Recall % | {recall['recall_pct']:.1f}% |",
        f"| Missing | {recall['missing']} |",
        f"| Noise | {recall['noise']} |",
        f"| Wall-clock | {elapsed:.1f}s |",
        "",
        "## Baseline Comparison",
        "",
        "| Strategy | Recall % | Notes |",
        "|----------|----------|-------|",
        "| HTTP BFS Strategy C (Phase A) | 67.2% | crawl4ai BFSDeepCrawlStrategy |",
        "| Playwright BFS 05 (Phase A) | 81.3% | 248/305, /de/rest/ filter |",
        f"| __NEXT_DATA__ union (this run) | {recall['recall_pct']:.1f}% | Pure HTTP, ~{elapsed:.0f}s |",
        "",
        "## Discovery Log",
        "",
    ] + log

    if recall["missing_urls"]:
        lines += [
            "",
            f"## All Missing URLs ({recall['missing']})",
            "",
        ]
        for u in sorted(recall["missing_urls"]):
            lines.append(f"- {u}")

    return "\n".join(lines)


# Save report to md/
def save_report(report: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"06_gh_live_discovery_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    path.write_text(report, encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="__NEXT_DATA__ nav-tree discovery probe")
    parser.add_argument("--gold", type=Path, default=GOLD_DEFAULT)
    parser.add_argument("--no-ghec", action="store_true", help="Skip GHEC sidebar fetch")
    parser.add_argument("--no-ghes", action="store_true", help="Skip GHES sidebar fetch")
    args = parser.parse_args()

    result = nextdata_discovery_workflow(
        gold_path=args.gold,
        include_ghec=not args.no_ghec,
        include_ghes=not args.no_ghes,
    )
    print("\n".join(result["log"]))
