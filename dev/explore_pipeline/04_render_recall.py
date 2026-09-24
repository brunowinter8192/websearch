# INFRASTRUCTURE
import argparse
import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, ContentTypeFilter

SEED_URL = "https://docs.github.com/de/rest"
DEFAULT_MAX_PAGES = 600
DEFAULT_DEPTH = 10
AGENT_TASKS_URL = "https://docs.github.com/de/rest/agent-tasks/agent-tasks"
MISSING_SAMPLE = 20
RECOVERED_SAMPLE = 30

GOLD_DEFAULT = Path(__file__).parent / "goldstandard" / "docs_github_rest.txt"
OUTPUT_DIR = Path(__file__).parent / "md"

STRATEGIES = [
    ("A_prefetch_domcontentloaded", {"prefetch": True,  "wait_until": "domcontentloaded"}),
    ("B_prefetch_networkidle",      {"prefetch": True,  "wait_until": "networkidle"}),
    ("C_bfs_networkidle",           {"prefetch": False, "wait_until": "networkidle"}),
]

REGRESSION_DOMAINS = [
    ("searxng_docs",  "https://docs.searxng.org",                                    2, 50),
    ("chroma_docs",   "https://docs.trychroma.com/docs/overview/telemetry",          2, 30),
]


# ORCHESTRATOR

async def render_recall_workflow(gold_path: Path, max_pages: int, depth: int,
                               no_regression: bool, only_strategies: list[str] | None = None,
                               delay_between: int = 0):
    gold = load_gold(gold_path)
    print(f"Gold standard: {len(gold)} URLs from {gold_path.name}")

    domain = urlparse(SEED_URL).netloc
    main_results = {}
    active = [(n, c) for n, c in STRATEGIES if only_strategies is None or n in only_strategies]

    for i, (name, cfg) in enumerate(active):
        if i > 0 and delay_between > 0:
            print(f"\nWaiting {delay_between}s between strategies...")
            await asyncio.sleep(delay_between)
        print(f"\n{'=' * 60}")
        print(f"Strategy: {name}  (prefetch={cfg['prefetch']}, wait_until={cfg['wait_until']})")
        urls, elapsed = await discover_with_config(
            SEED_URL, domain, max_pages, depth,
            cfg["wait_until"], cfg["prefetch"],
        )
        stats = compute_recall(urls, gold)
        stats["elapsed_s"] = round(elapsed, 1)
        stats["per_page_ms"] = round(elapsed / max(stats["found"], 1) * 1000)
        main_results[name] = stats
        print(f"  Found={stats['found']}  Recall={stats['recall_pct']:.1f}%  "
              f"Missing={stats['missing']}  Noise={stats['noise']}  Time={stats['elapsed_s']}s")

    regression_rows = []
    if not no_regression:
        regression_rows = await run_regression()

    report = format_report(gold, main_results, regression_rows)
    out_path = save_report(report)
    print(f"\n{report}")
    print(f"\nReport saved: {out_path}")


# FUNCTIONS

def load_gold(path: Path) -> frozenset:
    with open(path, encoding="utf-8") as f:
        return frozenset(normalize_url(ln.strip()) for ln in f if ln.strip())


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r'/[^/]*@[^/]+', '', parsed.path)
    path = path.rstrip('/')
    return f"{parsed.scheme}://{parsed.netloc}{path}"


async def discover_with_config(url: str, domain: str, max_pages: int, depth: int,
                               wait_until: str, use_prefetch: bool) -> tuple[list[str], float]:
    filters = [
        DomainFilter(allowed_domains=[domain]),
        ContentTypeFilter(allowed_types=["text/html"]),
    ]

    bfs = BFSDeepCrawlStrategy(
        max_depth=depth,
        include_external=False,
        filter_chain=FilterChain(filters),
        max_pages=max_pages,
    )
    run_kwargs: dict = dict(
        deep_crawl_strategy=bfs,
        cache_mode=CacheMode.BYPASS,
        wait_until=wait_until,
        verbose=False,
    )
    if use_prefetch:
        run_kwargs["prefetch"] = True

    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(**run_kwargs)

    t0 = time.time()
    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(url=url, config=run_config)
    elapsed = time.time() - t0

    if not isinstance(results, list):
        results = [results]

    seen: set[str] = set()
    urls: list[str] = []
    for r in results:
        raw = getattr(r, "url", None)
        if not raw:
            continue
        norm = normalize_url(raw)
        if norm not in seen:
            seen.add(norm)
            urls.append(norm)
    return urls, elapsed


def compute_recall(found_urls: list[str], gold: frozenset) -> dict:
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
        "missing_sample": sorted(missing)[:MISSING_SAMPLE],
        "found_urls": found_set,
    }


async def run_regression() -> list[dict]:
    print(f"\n{'=' * 60}")
    print("Regression check (non-SPA domains)")
    a_cfg = STRATEGIES[0][1]
    c_cfg = STRATEGIES[2][1]
    rows = []
    for label, url, depth, max_pages in REGRESSION_DOMAINS:
        domain = urlparse(url).netloc
        for strat_name, cfg in [("A", a_cfg), ("C", c_cfg)]:
            print(f"  {label}/{strat_name} ...", end=" ", flush=True)
            urls, elapsed = await discover_with_config(
                url, domain, max_pages, depth, cfg["wait_until"], cfg["prefetch"]
            )
            print(f"{len(urls)} URLs in {elapsed:.1f}s")
            rows.append({
                "domain": label, "strategy": strat_name,
                "found": len(urls), "elapsed_s": round(elapsed, 1),
                "per_page_ms": round(elapsed / max(len(urls), 1) * 1000),
            })
    return rows


def format_report(gold: frozenset, main_results: dict, regression_rows: list[dict]) -> str:
    lines = _format_main_results_table(gold, main_results)
    lines += _format_key_url_check(main_results)
    lines += _format_recovery_analysis(gold, main_results)
    lines += _format_best_strategy_missing(main_results)
    lines += _format_regression_check(regression_rows)
    return "\n".join(lines)


def _format_main_results_table(gold: frozenset, main_results: dict) -> list:
    lines = [
        "# Recall Probe — docs.github.com/de/rest",
        "",
        f"Seed: {SEED_URL}  |  Gold: {len(gold)} URLs",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Main Results",
        "",
        "| Strategy | Found | Matched | Recall % | Missing | Noise | Time (s) | ms/page |",
        "|----------|-------|---------|----------|---------|-------|----------|---------|",
    ]
    for name, s in main_results.items():
        lines.append(
            f"| {name} | {s['found']} | {s['matched']} | {s['recall_pct']:.1f}% "
            f"| {s['missing']} | {s['noise']} | {s['elapsed_s']} | {s['per_page_ms']} |"
        )
    return lines


def _format_key_url_check(main_results: dict) -> list:
    lines = ["", "## Key URL Check", ""]
    for name, s in main_results.items():
        hit = "FOUND" if AGENT_TASKS_URL in s["found_urls"] else "MISSING"
        lines.append(f"- `agent-tasks/agent-tasks` in {name}: **{hit}**")
    return lines


def _format_recovery_analysis(gold: frozenset, main_results: dict) -> list:
    lines = []
    a_found = main_results.get("A_prefetch_domcontentloaded", {}).get("found_urls", set())
    for cand_name in ["B_prefetch_networkidle", "C_bfs_networkidle"]:
        if cand_name not in main_results:
            continue
        cand_found = main_results[cand_name].get("found_urls", set())
        recovered = sorted(cand_found - a_found)
        lines += [
            "",
            f"## Recovered by {cand_name} (in gold, missed by A)",
            "",
            f"Count: {len(set(recovered) & gold)} in-gold  |  {len(recovered)} total (incl. noise)",
            "",
        ]
        in_gold = sorted(set(recovered) & gold)
        for u in in_gold[:RECOVERED_SAMPLE]:
            lines.append(f"- {u}")
        if len(in_gold) > RECOVERED_SAMPLE:
            lines.append(f"- ... ({len(in_gold) - RECOVERED_SAMPLE} more)")
    return lines


def _format_best_strategy_missing(main_results: dict) -> list:
    best_name = max(main_results, key=lambda n: main_results[n]["recall_pct"])
    lines = [
        "",
        f"## Still Missing from Best Strategy ({best_name})",
        "",
        f"Sample (up to {MISSING_SAMPLE} of {main_results[best_name]['missing']} total):",
        "",
    ]
    for u in main_results[best_name]["missing_sample"]:
        lines.append(f"- {u}")
    return lines


def _format_regression_check(regression_rows: list[dict]) -> list:
    lines = []
    if regression_rows:
        lines += [
            "",
            "## Regression Check",
            "",
            "| Domain | Strategy | Found | Time (s) | ms/page |",
            "|--------|----------|-------|----------|---------|",
        ]
        for r in regression_rows:
            lines.append(
                f"| {r['domain']} | {r['strategy']} | {r['found']} | {r['elapsed_s']} | {r['per_page_ms']} |"
            )
    return lines


def save_report(report: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"04_docs_github_rest_{datetime.now().strftime('%Y%m%d')}.md"
    path.write_text(report, encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure URL discovery recall on docs.github.com/de/rest — 3 strategies vs gold standard"
    )
    parser.add_argument("--gold", type=Path, default=GOLD_DEFAULT,
                        help=f"Gold standard file (default: goldstandard/docs_github_rest.txt)")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help=f"Max pages per strategy (default: {DEFAULT_MAX_PAGES})")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                        help=f"BFS depth (default: {DEFAULT_DEPTH})")
    parser.add_argument("--no-regression", action="store_true",
                        help="Skip regression check on non-SPA domains")
    parser.add_argument("--strategies", type=str, default=None,
                        help="Comma-separated strategy names to run (default: all). e.g. C_bfs_networkidle")
    parser.add_argument("--delay", type=int, default=0,
                        help="Seconds to sleep between strategies (default: 0, use 600 to avoid rate limiting)")
    args = parser.parse_args()

    only = [s.strip() for s in args.strategies.split(",")] if args.strategies else None
    asyncio.run(render_recall_workflow(args.gold, args.max_pages, args.depth,
                                      args.no_regression, only, args.delay))
