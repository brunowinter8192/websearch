# INFRASTRUCTURE
import asyncio
import importlib
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path
from zoneinfo import available_timezones

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

crawl4ai = importlib.import_module("crawl4ai")
AsyncWebCrawler = crawl4ai.AsyncWebCrawler
BrowserConfig = crawl4ai.BrowserConfig
CrawlerRunConfig = crawl4ai.CrawlerRunConfig
CacheMode = crawl4ai.CacheMode
DefaultMarkdownGenerator = importlib.import_module(
    "crawl4ai.markdown_generation_strategy"
).DefaultMarkdownGenerator

URL_FILE = REPO_ROOT / "dev/news_pipeline/04_json/discover_filtered_20260607T195044Z.json"
SMOKE_DIR = REPO_ROOT / "dev/news_pipeline/smoke_output"
B1_RAW = SMOKE_DIR / "b1_raw"
B2_RAW = SMOKE_DIR / "b2_raw"
B1_REVIEW = SMOKE_DIR / "b1_regwall_review.md"
B2_REVIEW = SMOKE_DIR / "b2_regwall_review.md"

PAGE_TIMEOUT_MS = 15000
DELAY_BEFORE_RETURN_HTML = 0.5
CONCURRENCY = 8

REGWALL_MARKERS = [
    "sign up",
    "create a free account",
    "create an account",
    "already have an account",
    "subscribe",
    "register",
    "continue reading",
    "by signing up",
    "sign in to continue",
]


# ORCHESTRATOR

def main():
    urls = _load_urls(URL_FILE)
    print(f"Loaded {len(urls)} URLs", flush=True)

    print("\n--- Candidate B1: shared browser, per-URL timezone (fresh context) ---", flush=True)
    t0 = time.time()
    asyncio.run(_run_b1(urls, B1_RAW))
    b1_wall = int(time.time() - t0)

    print("\n--- Candidate B2: fresh crawler per URL (parallel, semaphore-gated) ---", flush=True)
    t0 = time.time()
    asyncio.run(_run_b2(urls, B2_RAW))
    b2_wall = int(time.time() - t0)

    b1_rows = _build_rows(urls, B1_RAW)
    b2_rows = _build_rows(urls, B2_RAW)

    _write_review(b1_rows, B1_REVIEW, "B1 — shared browser, fresh context per URL")
    _write_review(b2_rows, B2_REVIEW, "B2 — fresh crawler per URL (parallel)")

    _print_comparison(b1_rows, b1_wall, b2_rows, b2_wall)


# FUNCTIONS

def _load_urls(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item["url"] for item in data]


async def _run_b1(urls: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    zones = sorted(available_timezones())
    assert len(zones) >= len(urls), f"Need {len(urls)} timezones, have {len(zones)}"
    sem = asyncio.Semaphore(CONCURRENCY)
    browser_cfg = BrowserConfig(headless=True, verbose=False)

    async def fetch_one(crawler: AsyncWebCrawler, url: str, zone: str) -> None:
        async with sem:
            jitter = random.uniform(0.5, 1.0)
            await asyncio.sleep(jitter)
            run_cfg = _base_run_cfg(timezone_id=zone)
            try:
                result = await crawler.arun(url=url, config=run_cfg)
                raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""
                _save(url, raw_md, output_dir)
                print(f"  B1 ok  {len(raw_md):>7} bytes  {url.split('/')[-1][:60]}", flush=True)
            except Exception as e:
                print(f"  B1 ERR {url.split('/')[-1][:60]}: {e}", flush=True)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        await asyncio.gather(*[fetch_one(crawler, url, zones[i]) for i, url in enumerate(urls)])


async def _run_b2(urls: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    run_cfg = _base_run_cfg()

    async def fetch_one(url: str) -> None:
        async with sem:
            jitter = random.uniform(0.5, 1.0)
            await asyncio.sleep(jitter)
            browser_cfg = BrowserConfig(headless=True, verbose=False)
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                try:
                    result = await crawler.arun(url=url, config=run_cfg)
                    raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""
                    _save(url, raw_md, output_dir)
                    print(f"  B2 ok  {len(raw_md):>7} bytes  {url.split('/')[-1][:60]}", flush=True)
                except Exception as e:
                    print(f"  B2 ERR {url.split('/')[-1][:60]}: {e}", flush=True)

    await asyncio.gather(*[fetch_one(url) for url in urls])


def _build_rows(urls: list[str], output_dir: Path) -> list[dict]:
    file_by_url: dict[str, Path] = {}
    for fpath in output_dir.glob("*.md"):
        text = fpath.read_text(encoding="utf-8", errors="replace")
        first_line = text.split("\n", 1)[0].strip()
        m = re.match(r"<!--\s*source:\s*(.+?)\s*-->", first_line)
        if m:
            file_by_url[m.group(1)] = fpath

    rows = []
    for url in urls:
        fpath = file_by_url.get(url)
        if fpath is None:
            rows.append({"url": url, "found": False, "bytes": 0,
                         "lines": 0, "marker_hits": 0, "verdict": "MISSING", "content_lines": []})
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        byte_count = len(text.encode("utf-8"))
        all_lines = text.splitlines()
        lower_text = text.lower()
        hits = sum(lower_text.count(m) for m in REGWALL_MARKERS)
        verdict = "REGWALL?" if (byte_count < 3000 or hits >= 3) else "article?"
        rows.append({"url": url, "found": True, "bytes": byte_count,
                     "lines": len(all_lines), "marker_hits": hits,
                     "verdict": verdict, "content_lines": all_lines})
    return rows


def _write_review(rows: list[dict], out_path: Path, title: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        f"# CoinDesk Isolation Smoke — {title}",
        "",
        "> verdict_hint: `REGWALL?` if bytes<3000 OR marker_hits>=3, else `article?`. Judge by eye.",
        "",
        "## Summary Table",
        "",
        "| slug | bytes | lines | marker_hits | verdict_hint |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        slug = row["url"].rstrip("/").split("/")[-1][:60]
        parts.append(f"| {slug} | {row['bytes']} | {row['lines']} | {row['marker_hits']} | {row['verdict']} |")

    parts += ["", "---", ""]

    for row in rows:
        parts.append(f"## {row['url']}")
        parts.append("")
        if not row["found"]:
            parts.append("**NO FILE — scrape produced no output (error or empty).**")
            parts.append("")
            continue
        parts.append(f"bytes: {row['bytes']} | lines: {row['lines']} | marker_hits: {row['marker_hits']} | verdict_hint: {row['verdict']}")
        parts.append("")
        parts.append("```")
        parts.extend(row["content_lines"][:50])
        parts.append("```")
        parts.append("")

    out_path.write_text("\n".join(parts), encoding="utf-8")


def _print_comparison(b1_rows: list[dict], b1_wall: int,
                      b2_rows: list[dict], b2_wall: int) -> None:
    def stats(rows: list[dict]) -> tuple[int, int, int]:
        ok = sum(1 for r in rows if r["found"])
        rw = sum(1 for r in rows if r["verdict"] == "REGWALL?")
        clean = sum(1 for r in rows if r["verdict"] == "article?")
        return ok, rw, clean

    b1_ok, b1_rw, b1_clean = stats(b1_rows)
    b2_ok, b2_rw, b2_clean = stats(b2_rows)

    b1_bytes = [r["bytes"] for r in b1_rows if r["found"]]
    b2_bytes = [r["bytes"] for r in b2_rows if r["found"]]

    print("\n=== COMPARISON TABLE ===")
    print("| approach | ok | regwall | clean | wallclock_s |")
    print("|---|---|---|---|---|")
    print(f"| prod-baseline (Smoke A) | 32 | 17 | 15 | 31 |")
    print(f"| B1 shared-browser + timezone-bust | {b1_ok} | {b1_rw} | {b1_clean} | {b1_wall} |")
    print(f"| B2 fresh-crawler-per-URL parallel | {b2_ok} | {b2_rw} | {b2_clean} | {b2_wall} |")

    if b1_bytes:
        print(f"\nB1 bytes: min={min(b1_bytes)} median={int(statistics.median(b1_bytes))} max={max(b1_bytes)}")
    if b2_bytes:
        print(f"B2 bytes: min={min(b2_bytes)} median={int(statistics.median(b2_bytes))} max={max(b2_bytes)}")

    print(f"\nB1 review: {B1_REVIEW}")
    print(f"B2 review: {B2_REVIEW}")


def _base_run_cfg(timezone_id: str = "") -> CrawlerRunConfig:
    kwargs = dict(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_BEFORE_RETURN_HTML,
        page_timeout=PAGE_TIMEOUT_MS,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    if timezone_id:
        kwargs["timezone_id"] = timezone_id
    return CrawlerRunConfig(**kwargs)


def _save(url: str, raw_md: str, output_dir: Path) -> int:
    if not raw_md:
        return 0
    content = f"<!-- source: {url} -->\n\n{raw_md}"
    (output_dir / _url_to_filename(url)).write_text(content, encoding="utf-8")
    return len(content.encode("utf-8"))


def _url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:100]
    return f"{slug}.md"


if __name__ == "__main__":
    main()
