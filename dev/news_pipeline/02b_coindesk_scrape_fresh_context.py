#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

REGWALL_FAIL_THRESHOLD = 0.20

DOWNLOAD_DELAY = 1.0
CONCURRENCY_PER_DOMAIN = 8
PAGE_TIMEOUT_MS = 15000
DELAY_BEFORE_RETURN_HTML = 0.5

REGWALL_SIGNALS = [
    "from_regwall",
    "Create a FREE account to continue reading",
    "You've reached your monthly limit",
]

INPUT_DIR = Path(__file__).parent / "01_json"
OUTPUT_DIR = Path(__file__).parent / "02b_data"

_RUN_CFG = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    wait_until="domcontentloaded",
    delay_before_return_html=DELAY_BEFORE_RETURN_HTML,
    page_timeout=PAGE_TIMEOUT_MS,
    markdown_generator=DefaultMarkdownGenerator(),
    verbose=False,
)


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description=(
            "CoinDesk raw scrape — fresh AsyncWebCrawler per URL, concurrent via asyncio.gather, "
            "prod Scrapy gate (~1 req/s per domain, deterministic), loud regwall guard."
        )
    )
    parser.add_argument(
        "--input", default=None,
        help="Path to discover_*.json (default: newest in 01_json/)"
    )
    args = parser.parse_args()
    input_path = _compute_input_path(args)
    asyncio.run(scrape_workflow(input_path))


# FUNCTIONS

def _compute_input_path(args):
    input_path = Path(args.input) if args.input else pick_latest_input()
    return input_path


async def scrape_workflow(input_path: Path) -> None:
    entries = load_entries(input_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Input : {input_path} ({len(entries)} URLs)", file=sys.stderr)
    print(f"Output: {OUTPUT_DIR}", file=sys.stderr)

    domain_states: dict = {}
    t_start = time.perf_counter()

    raw_results = await asyncio.gather(
        *[_fetch_one(domain_states, entries[i], i, len(entries)) for i in range(len(entries))],
        return_exceptions=True,
    )

    manifest = _collect_manifest(entries, raw_results)
    _check_regwall_guard(manifest)
    write_manifest(manifest)
    print_summary(manifest, time.perf_counter() - t_start)


def pick_latest_input() -> Path:
    candidates = sorted(INPUT_DIR.glob("discover_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No discover_*.json found in {INPUT_DIR}")
    return candidates[-1]


def load_entries(input_path: Path) -> list[dict]:
    return json.loads(input_path.read_text(encoding="utf-8"))


async def _fetch_one(
    domain_states: dict,
    entry: dict,
    idx: int,
    total: int,
) -> dict:
    url = entry["url"]
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    result_entry: dict = {
        "url": url, "hash": url_hash, "file": None,
        "char_count": None, "status": None, "error": None, "wait_strategy": None,
    }
    domain = urlparse(url).netloc
    state = _ensure_domain_state(domain_states, domain, CONCURRENCY_PER_DOMAIN)
    async with state["sem"]:
        await _gate_domain(state, DOWNLOAD_DELAY)
        print(f"[{idx + 1}/{total}] {url}", file=sys.stderr)
        t0 = time.perf_counter()
        try:
            async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as crawler:
                result = await crawler.arun(url=url, config=_RUN_CFG)
            elapsed = time.perf_counter() - t0
            raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""

            if _is_regwall(raw_md):
                result_entry.update({
                    "status": "regwall", "char_count": len(raw_md),
                    "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
                })
                print(f"  WARN regwall detected — skipping write: {url}", file=sys.stderr)
            elif not raw_md:
                result_entry.update({
                    "status": "empty", "char_count": 0,
                    "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
                })
                print(f"  empty ({elapsed:.1f}s)", file=sys.stderr)
            else:
                file_path = write_article(entry, url_hash, raw_md)
                result_entry.update({
                    "status": "ok", "char_count": len(raw_md),
                    "file": str(file_path.relative_to(Path.cwd()) if file_path.is_absolute() else file_path),
                    "elapsed_s": round(elapsed, 2), "wait_strategy": "domcontentloaded",
                })
                print(f"  ok — {len(raw_md):,} chars in {elapsed:.1f}s [domcontentloaded]", file=sys.stderr)
        except Exception as exc:
            result_entry.update({"status": "failed", "error": str(exc)})
            print(f"  FAILED: {exc}", file=sys.stderr)
    return result_entry


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


def _check_regwall_guard(manifest: list[dict]) -> None:
    regwalled = [e for e in manifest if e["status"] == "regwall"]
    if not regwalled:
        return
    print(f"WARNING: {len(regwalled)} regwall(s) detected:", file=sys.stderr)
    for e in regwalled:
        print(f"  REGWALL {e['url']}", file=sys.stderr)
    total = len(manifest)
    if total > 0 and len(regwalled) / total >= REGWALL_FAIL_THRESHOLD:
        print(
            f"ERROR: isolation likely broken — {len(regwalled)}/{total} regwalled"
            f" (>= {REGWALL_FAIL_THRESHOLD:.0%} threshold). Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)


def write_manifest(manifest: list[dict]) -> None:
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {manifest_path}", file=sys.stderr)


def print_summary(manifest: list[dict], total_s: float) -> None:
    ok = [e for e in manifest if e["status"] == "ok"]
    ok_fb = [e for e in manifest if e["status"] == "ok_fallback"]
    failed = [e for e in manifest if e["status"] == "failed"]
    empty = [e for e in manifest if e["status"] == "empty"]
    regwall_e = [e for e in manifest if e["status"] == "regwall"]
    all_ok = ok + ok_fb
    total_chars = sum(e["char_count"] or 0 for e in all_ok)
    slowest = max(all_ok, key=lambda e: e.get("elapsed_s", 0), default=None)

    print(f"\nDone in {total_s:.0f}s")
    print(f"  ok      : {len(all_ok)} ({len(ok_fb)} via fallback)")
    print(f"  empty   : {len(empty)}")
    print(f"  failed  : {len(failed)}")
    print(f"  regwall : {len(regwall_e)}")
    print(f"  total chars: {total_chars:,}")
    if slowest:
        print(f"  slowest : {slowest['url']} ({slowest.get('elapsed_s', '?')}s)")


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


def _is_regwall(markdown: str) -> bool:
    return any(sig in markdown for sig in REGWALL_SIGNALS)


def write_article(entry: dict, url_hash: str, content: str) -> Path:
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = (
        "---\n"
        f"url: {entry['url']}\n"
        f"lastmod: {entry['lastmod']}\n"
        f"publication_date: {entry['publication_date']}\n"
        f"title: {entry['title']}\n"
        f"section: {entry['section']}\n"
        f"scraped_at: {scraped_at}\n"
        "---\n\n"
    )
    file_path = OUTPUT_DIR / f"{url_hash}.md"
    file_path.write_text(frontmatter + content, encoding="utf-8")
    return file_path


if __name__ == "__main__":
    main()
