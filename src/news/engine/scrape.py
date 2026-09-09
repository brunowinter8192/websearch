# INFRASTRUCTURE
import asyncio
import hashlib
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from src.news.platform import ScrapeConfig

REGWALL_FAIL_THRESHOLD = 0.20


# ORCHESTRATOR

async def scrape_entries(
    entries: list[dict],
    output_dir: Path,
    regwall_signals: list[str],
    scrape_cfg: ScrapeConfig,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)

    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=scrape_cfg.delay_before_return_html,
        page_timeout=scrape_cfg.page_timeout_ms,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    domain_states: dict = {}
    raw_results = await asyncio.gather(
        *[
            _fetch_one(domain_states, entries[i], i, len(entries),
                       regwall_signals, scrape_cfg, output_dir, run_cfg)
            for i in range(len(entries))
        ],
        return_exceptions=True,
    )

    manifest = _collect_manifest(entries, raw_results)
    _check_regwall_guard(manifest, regwall_signals)
    return manifest


# FUNCTIONS

def _is_regwall(markdown: str, signals: list[str]) -> bool:
    return any(sig in markdown for sig in signals)


def _ensure_domain_state(domain_states: dict, domain: str, concurrency_per_domain: int) -> dict:
    if domain not in domain_states:
        domain_states[domain] = {
            "lastseen": 0.0,
            "lock": asyncio.Lock(),
            "sem": asyncio.Semaphore(concurrency_per_domain),
        }
    return domain_states[domain]


async def _gate_domain(state: dict, download_delay: float) -> None:
    async with state["lock"]:
        jitter = random.uniform(0.5 * download_delay, 1.5 * download_delay)
        now = time.time()
        gap = now - state["lastseen"]
        if gap < jitter:
            await asyncio.sleep(jitter - gap)
        state["lastseen"] = time.time()


async def _fetch_one(
    domain_states: dict,
    entry: dict,
    idx: int,
    total: int,
    regwall_signals: list[str],
    scrape_cfg: ScrapeConfig,
    output_dir: Path,
    run_cfg: CrawlerRunConfig,
) -> dict:
    url = entry["url"]
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    result_entry: dict = {
        "url": url, "hash": url_hash, "file": None,
        "char_count": None, "status": None, "error": None, "wait_strategy": None,
    }
    domain = urlparse(url).netloc
    state = _ensure_domain_state(domain_states, domain, scrape_cfg.concurrency_per_domain)
    async with state["sem"]:
        await _gate_domain(state, scrape_cfg.download_delay)
        print(f"[{idx + 1}/{total}] {url}", file=sys.stderr)
        t0 = time.perf_counter()
        try:
            async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as crawler:
                result = await crawler.arun(url=url, config=run_cfg)
            elapsed = time.perf_counter() - t0
            raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""
            result_entry.update(_classify_fetch(url, url_hash, raw_md, elapsed, regwall_signals, output_dir))
        except Exception as exc:
            result_entry.update({"status": "failed", "error": str(exc)})
            print(f"  FAILED: {exc}", file=sys.stderr)
    return result_entry


def _classify_fetch(
    url: str, url_hash: str, raw_md: str, elapsed: float,
    regwall_signals: list[str], output_dir: Path,
) -> dict:
    if _is_regwall(raw_md, regwall_signals):
        print(f"  WARN regwall detected — skipping write: {url}", file=sys.stderr)
        return {
            "status": "regwall", "char_count": len(raw_md),
            "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
        }
    if not raw_md:
        print(f"  empty ({elapsed:.1f}s)", file=sys.stderr)
        return {
            "status": "empty", "char_count": 0,
            "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
        }
    file_path = _write_body(url_hash, raw_md, output_dir)
    print(f"  ok — {len(raw_md):,} chars in {elapsed:.1f}s [domcontentloaded]", file=sys.stderr)
    return {
        "status": "ok", "char_count": len(raw_md), "file": str(file_path),
        "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
    }


def _write_body(url_hash: str, content: str, output_dir: Path) -> Path:
    file_path = output_dir / f"{url_hash}.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _collect_manifest(entries: list[dict], raw_results: tuple) -> list[dict]:
    manifest = []
    for i, r in enumerate(raw_results):
        if isinstance(r, dict):
            manifest.append(r)
        else:
            url = entries[i]["url"]
            manifest.append({
                "url": url, "hash": hashlib.sha256(url.encode()).hexdigest()[:12],
                "file": None, "char_count": None,
                "status": "failed", "error": str(r), "wait_strategy": None,
            })
    return manifest


class RegwallGuardError(Exception):
    def __init__(self, msg: str, manifest: list[dict] | None = None):
        super().__init__(msg)
        self.manifest: list[dict] = manifest or []


def _check_regwall_guard(manifest: list[dict], regwall_signals: list[str]) -> None:
    if not regwall_signals:
        return
    regwalled = [e for e in manifest if e["status"] == "regwall"]
    if not regwalled:
        return
    print(f"WARNING: {len(regwalled)} regwall(s) detected:", file=sys.stderr)
    for e in regwalled:
        print(f"  REGWALL {e['url']}", file=sys.stderr)
    total = len(manifest)
    if total > 0 and len(regwalled) / total >= REGWALL_FAIL_THRESHOLD:
        msg = (
            f"isolation likely broken — {len(regwalled)}/{total} regwalled"
            f" (>= {REGWALL_FAIL_THRESHOLD:.0%} threshold)"
        )
        print(f"ERROR: {msg}", file=sys.stderr)
        raise RegwallGuardError(msg, manifest=manifest)
