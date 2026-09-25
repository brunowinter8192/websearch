#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
INPUT_DIR = Path(__file__).parent / "01_json"
OUTPUT_DIR = Path(__file__).parent / "02_output"


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk raw scrape — reads discover JSON, writes per-article .md with YAML frontmatter."
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


async def scrape_workflow(input_path: Path):
    entries = load_entries(input_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Input : {input_path} ({len(entries)} URLs)", file=sys.stderr)
    print(f"Output: {OUTPUT_DIR}", file=sys.stderr)

    browser_config = BrowserConfig(headless=True, verbose=False, user_agent=USER_AGENT)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    manifest = []
    t_start = time.perf_counter()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, entry in enumerate(entries, 1):
            result_entry = await scrape_one_url(crawler, entry, run_config, i, len(entries))
            manifest.append(result_entry)
            await asyncio.sleep(1.0)

    write_manifest(manifest)
    print_summary(manifest, time.perf_counter() - t_start)


def pick_latest_input() -> Path:
    candidates = sorted(INPUT_DIR.glob("discover_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No discover_*.json found in {INPUT_DIR}")
    return candidates[-1]


def load_entries(input_path: Path) -> list[dict]:
    return json.loads(input_path.read_text(encoding="utf-8"))


async def scrape_one_url(crawler: AsyncWebCrawler, entry: dict, run_config: CrawlerRunConfig,
                          i: int, total: int) -> dict:
    url = entry["url"]
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    print(f"[{i}/{total}] {url}", file=sys.stderr)

    result_entry = scrape_one(entry, url_hash)
    try:
        t0 = time.perf_counter()
        result = await crawler.arun(url=url, config=run_config)
        elapsed = time.perf_counter() - t0
        content = result.markdown.raw_markdown if result.markdown else ""
        if content:
            file_path = write_article(entry, url_hash, content)
            result_entry.update({
                "status": "ok",
                "char_count": len(content),
                "file": str(file_path.relative_to(Path.cwd()) if file_path.is_absolute() else file_path),
                "elapsed_s": round(elapsed, 2),
            })
            print(f"  ok — {len(content):,} chars in {elapsed:.1f}s", file=sys.stderr)
        else:
            result_entry.update({"status": "empty", "char_count": 0, "elapsed_s": round(elapsed, 2)})
            print(f"  empty ({elapsed:.1f}s)", file=sys.stderr)
    except Exception as exc:
        result_entry.update({"status": "failed", "error": str(exc)})
        print(f"  FAILED: {exc}", file=sys.stderr)

    return result_entry


def write_manifest(manifest: list[dict]):
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {manifest_path}", file=sys.stderr)


def print_summary(manifest: list[dict], total_s: float):
    ok = [e for e in manifest if e["status"] == "ok"]
    failed = [e for e in manifest if e["status"] == "failed"]
    empty = [e for e in manifest if e["status"] == "empty"]
    total_chars = sum(e["char_count"] or 0 for e in ok)
    slowest = max(ok, key=lambda e: e.get("elapsed_s", 0), default=None)

    print(f"\nDone in {total_s:.0f}s")
    print(f"  ok      : {len(ok)}")
    print(f"  empty   : {len(empty)}")
    print(f"  failed  : {len(failed)}")
    print(f"  total chars: {total_chars:,}")
    if slowest:
        print(f"  slowest : {slowest['url']} ({slowest.get('elapsed_s', '?')}s)")


def scrape_one(entry: dict, url_hash: str) -> dict:
    return {
        "url": entry["url"],
        "hash": url_hash,
        "file": None,
        "char_count": None,
        "status": None,
        "error": None,
    }


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
