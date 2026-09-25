# INFRASTRUCTURE
import asyncio
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

URL_FILE = Path("dev/explore_pipeline/06_discovered_urls.txt")
GAP_SECONDS = 300
DOWNLOAD_DELAY = 1.0
CONCURRENCY_PER_DOMAIN = 8
PAGE_TIMEOUT_MS = 15000
DELAY_BEFORE_RETURN_HTML = 0.5
EMPTY_THRESHOLD_BYTES = 100
JSON_DIR = Path("dev/pipe_scraper_hardening/json")
MD_DIR = Path("dev/pipe_scraper_hardening/md")
OUTCOME_KEYS = ["ok", "waf_429", "http_error", "empty", "error"]


# ORCHESTRATOR

async def probe_workflow() -> Path:
    urls = _load_urls()
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)

    baseline = await _run_variant("baseline", urls, enable_stealth=False)
    _save_json("baseline", baseline)
    print(f"baseline done: {_summarize(baseline['results'])} wall={baseline['wall_s']:.0f}s")

    print(f"sleeping {GAP_SECONDS}s before stealth run (WAF budget recovery gap)")
    await asyncio.sleep(GAP_SECONDS)

    stealth = await _run_variant("stealth", urls, enable_stealth=True)
    _save_json("stealth", stealth)
    print(f"stealth done: {_summarize(stealth['results'])} wall={stealth['wall_s']:.0f}s")

    report_path = _write_report(baseline, stealth)
    print(f"report: {report_path}")
    return report_path


# FUNCTIONS

def _load_urls() -> list[str]:
    return [ln.strip() for ln in URL_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]


async def _run_variant(label: str, urls: list[str], enable_stealth: bool) -> dict:
    output_dir = Path(f"/tmp/pipe_scraper_hardening_{label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    crash_log: list = []
    t0 = time.time()
    results = await _scrape_all(
        urls, output_dir, DOWNLOAD_DELAY, CONCURRENCY_PER_DOMAIN, enable_stealth, crash_log,
    )
    wall_s = time.time() - t0
    return {"label": label, "enable_stealth": enable_stealth, "results": results,
            "wall_s": wall_s, "crash_log": crash_log}


def _save_json(label: str, run: dict) -> None:
    path = JSON_DIR / f"01_{label}_results.json"
    payload = {"label": run["label"], "enable_stealth": run["enable_stealth"],
               "wall_s": run["wall_s"], "crash_log": run["crash_log"], "results": run["results"]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_report(baseline: dict, stealth: dict) -> Path:
    b_summary = _summarize(baseline["results"])
    s_summary = _summarize(stealth["results"])
    byte_cmp = _byte_comparison(baseline["results"], stealth["results"])
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = MD_DIR / f"01_stealth_concurrency_probe_{date}.md"

    lines = [
        f"# Stealth-at-concurrency-8 probe — {date}",
        "",
        f"Dataset: `{URL_FILE}` (316 URLs). Config held constant across both runs: "
        f"`DOWNLOAD_DELAY={DOWNLOAD_DELAY}`, `CONCURRENCY_PER_DOMAIN={CONCURRENCY_PER_DOMAIN}`, "
        f"`page_timeout={PAGE_TIMEOUT_MS}`, `delay_before_return_html={DELAY_BEFORE_RETURN_HTML}`. "
        f"Order: baseline run first, then stealth, gap = {GAP_SECONDS}s between runs.",
        "",
        "## Outcome breakdown",
        "",
        "| variant | ok | waf_429 | http_error | empty | error | wall_s |",
        "|---|---|---|---|---|---|---|",
        f"| baseline | {b_summary['ok']} | {b_summary['waf_429']} | {b_summary['http_error']} | "
        f"{b_summary['empty']} | {b_summary['error']} | {baseline['wall_s']:.0f} |",
        f"| stealth | {s_summary['ok']} | {s_summary['waf_429']} | {s_summary['http_error']} | "
        f"{s_summary['empty']} | {s_summary['error']} | {stealth['wall_s']:.0f} |",
        "",
        "## Crash / exception signatures",
        "",
        "Baseline:",
        "```",
        *(baseline["crash_log"] or ["(none)"]),
        "```",
        "",
        "Stealth:",
        "```",
        *(stealth["crash_log"] or ["(none)"]),
        "```",
        "",
        "## Byte-count comparison (stealth vs baseline, per URL)",
        "",
        f"- URLs compared: {byte_cmp['compared']}",
        f"- Identical byte count: {byte_cmp['identical']}",
        f"- Changed byte count: {byte_cmp['changed']}",
        f"- Mean delta (stealth - baseline): {byte_cmp['mean_delta']:.1f} bytes",
        f"- Max |delta|: {byte_cmp['max_abs_delta']} bytes at `{byte_cmp['max_abs_delta_url']}`",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _summarize(results: list[dict]) -> dict:
    return {k: sum(1 for r in results if r["outcome"] == k) for k in OUTCOME_KEYS}


async def _scrape_all(
    urls: list[str],
    output_dir: Path,
    download_delay: float,
    concurrency_per_domain: int,
    enable_stealth: bool,
    crash_log: list,
) -> list[dict]:
    browser_cfg = BrowserConfig(headless=True, verbose=False, enable_stealth=enable_stealth)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_BEFORE_RETURN_HTML,
        page_timeout=PAGE_TIMEOUT_MS,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    domain_states: dict = {}
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        raw = await asyncio.gather(
            *[_scrape_one(crawler, url, run_cfg, domain_states,
                          download_delay, concurrency_per_domain, output_dir, crash_log)
              for url in urls],
            return_exceptions=True,
        )
    results = [
        r if isinstance(r, dict)
        else {'url': urls[i], 'outcome': 'error', 'wall_ms': 0, 'bytes': 0, 'status_code': None}
        for i, r in enumerate(raw)
    ]
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            crash_log.append(f"{urls[i]}: gather-level {type(r).__name__}: {r}")
    return results


def _byte_comparison(baseline_results: list[dict], stealth_results: list[dict]) -> dict:
    b_by_url = {r["url"]: r["bytes"] for r in baseline_results}
    s_by_url = {r["url"]: r["bytes"] for r in stealth_results}
    common = set(b_by_url) & set(s_by_url)
    diffs = {u: s_by_url[u] - b_by_url[u] for u in common}
    changed = {u: d for u, d in diffs.items() if d != 0}
    return {
        "compared": len(common),
        "identical": len(common) - len(changed),
        "changed": len(changed),
        "mean_delta": (sum(diffs.values()) / len(diffs)) if diffs else 0.0,
        "max_abs_delta_url": max(diffs, key=lambda u: abs(diffs[u])) if diffs else None,
        "max_abs_delta": max(diffs.values(), key=abs) if diffs else 0,
    }


async def _scrape_one(
    crawler: AsyncWebCrawler,
    url: str,
    run_cfg: CrawlerRunConfig,
    domain_states: dict,
    download_delay: float,
    concurrency_per_domain: int,
    output_dir: Path,
    crash_log: list,
) -> dict:
    domain = urlparse(url).netloc
    state = _ensure_domain_state(domain_states, domain, concurrency_per_domain)
    async with state['sem']:
        await _gate_domain(state, download_delay)
        t0 = time.time()
        try:
            result = await crawler.arun(url=url, config=run_cfg)
        except Exception as exc:
            crash_log.append(f"{url}: {type(exc).__name__}: {exc}")
            return {'url': url, 'wall_ms': int((time.time() - t0) * 1000),
                    'bytes': 0, 'status_code': None, 'outcome': 'error'}
        wall_ms = int((time.time() - t0) * 1000)

    raw_md = (result.markdown.raw_markdown if result.markdown else '') or ''
    status = getattr(result, 'status_code', None)
    byte_count = len(raw_md.encode('utf-8'))

    if status == 429:
        outcome = 'waf_429'
    elif status and status >= 400:
        outcome = 'http_error'
    elif byte_count < EMPTY_THRESHOLD_BYTES:
        outcome = 'empty'
    else:
        outcome = 'ok'

    if raw_md:
        fname = _url_to_filename(url)
        (output_dir / fname).write_text(f"<!-- source: {url} -->\n\n{raw_md}", encoding='utf-8')

    return {'url': url, 'wall_ms': wall_ms, 'bytes': byte_count,
            'status_code': status, 'outcome': outcome}


def _ensure_domain_state(domain_states: dict, domain: str, concurrency_per_domain: int) -> dict:
    if domain not in domain_states:
        domain_states[domain] = {
            'lastseen': 0.0,
            'lock': asyncio.Lock(),
            'sem': asyncio.Semaphore(concurrency_per_domain),
        }
    return domain_states[domain]


async def _gate_domain(state: dict, download_delay: float) -> None:
    async with state['lock']:
        jitter = random.uniform(0.5 * download_delay, 1.5 * download_delay)
        now = time.time()
        gap = now - state['lastseen']
        if gap < jitter:
            await asyncio.sleep(jitter - gap)
        state['lastseen'] = time.time()


def _url_to_filename(url: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]', '_', url.split('://')[-1])
    slug = re.sub(r'_+', '_', slug).strip('_')[:100]
    return f"{slug}.md"


if __name__ == "__main__":
    asyncio.run(probe_workflow())
