#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

QUERY_SECTION_RE = re.compile(r"^## Q(\d+): (.+)$")
ENTRY_RE = re.compile(r"^(\d+)\. \*\*\[([A-Z?]+)\]\*\*")
URL_LINE_RE = re.compile(r"^\s+URL: (https?://\S+)$")

WORKTREE_ROOT = Path(__file__).parent.parent.parent


# ORCHESTRATOR
async def raw_smoke_workflow(input_path: str, query_id: int, output_dir: str | None):
    query_text, url_entries = parse_smoke_report(input_path, query_id)
    out_dir = prepare_output_dir(output_dir)
    print(f"raw_smoke: Q{query_id} — {query_text}", file=sys.stderr)
    print(f"URLs: {len(url_entries)} | Output: {out_dir}", file=sys.stderr)

    start_time = time.time()
    results = await scrape_all(url_entries, out_dir)
    runtime = time.time() - start_time

    report_path = write_report(results, query_text, query_id, input_path, out_dir, runtime)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(results)} ok in {runtime:.0f}s", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)


# FUNCTIONS

def parse_smoke_report(input_path: str, query_id: int) -> tuple[str, list[tuple[int, str, str]]]:
    lines = Path(input_path).read_text(encoding="utf-8").splitlines()
    query_text, start, end = find_query_section(lines, query_id)
    return query_text, extract_urls(lines, start, end)


def find_query_section(lines: list[str], query_id: int) -> tuple[str, int, int]:
    start = -1
    query_text = ""
    for i, line in enumerate(lines):
        m = QUERY_SECTION_RE.match(line)
        if not m:
            continue
        if int(m.group(1)) == query_id:
            start = i
            query_text = m.group(2)
        elif start != -1:
            return query_text, start, i
    if start == -1:
        raise ValueError(f"Query Q{query_id} not found in smoke report")
    return query_text, start, len(lines)


def extract_urls(lines: list[str], start: int, end: int) -> list[tuple[int, str, str]]:
    entries = []
    current_pos, current_class = None, None
    for line in lines[start:end]:
        m = ENTRY_RE.match(line)
        if m:
            current_pos, current_class = int(m.group(1)), m.group(2)
            continue
        if current_pos is not None:
            um = URL_LINE_RE.match(line)
            if um:
                entries.append((current_pos, current_class, um.group(1)))
                current_pos, current_class = None, None
    return entries


def prepare_output_dir(output_dir: str | None) -> Path:
    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = WORKTREE_ROOT / "dev" / "scrape_pipeline" / "02_raw_data" / ts
    else:
        out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def sanitize_filename(url: str) -> str:
    slug = re.sub(r"[^\w]", "_", url)[:80]
    h = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{slug}_{h}"


async def scrape_all(url_entries: list[tuple[int, str, str]], out_dir: Path) -> list[dict]:
    urls = [url for _, _, url in url_entries]
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_until="networkidle")

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            raw_results = await crawler.arun_many(urls=urls, config=run_config)
    except Exception as e:
        return [
            {"pos": pos, "class_label": cl, "url": url,
             "status": f"exception: {type(e).__name__}", "filepath": None}
            for pos, cl, url in url_entries
        ]

    result_by_url: dict[str, object] = {r.url: r for r in raw_results}

    results = []
    for pos, class_label, url in url_entries:
        r = result_by_url.get(url)
        if r is None:
            results.append({"pos": pos, "class_label": class_label, "url": url,
                            "status": "exception: missing", "filepath": None})
            continue

        try:
            content = r.markdown.raw_markdown if r.markdown else None
        except Exception as e:
            results.append({"pos": pos, "class_label": class_label, "url": url,
                            "status": f"exception: {type(e).__name__}", "filepath": None})
            continue

        if not content:
            hint = _empty_hint(url)
            results.append({"pos": pos, "class_label": class_label, "url": url,
                            "status": f"empty{hint}", "filepath": None})
            continue

        filepath = out_dir / (sanitize_filename(url) + ".md")
        filepath.write_text(f"<!-- source: {url} -->\n\n{content}", encoding="utf-8")
        results.append({"pos": pos, "class_label": class_label, "url": url,
                        "status": "ok", "filepath": str(filepath)})

    return results


def _empty_hint(url: str) -> str:
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext == ".pdf":
        return " (PDF)"
    domain = url.split("/")[2] if "//" in url else ""
    plugin_domains = ("github.com", "arxiv.org", "reddit.com")
    for d in plugin_domains:
        if d in domain:
            return f" (plugin-domain: {d.split('.')[0]})"
    return ""


def write_report(
    results: list, query_text: str, query_id: int,
    input_path: str, out_dir: Path, runtime: float,
) -> Path:
    ok_count = sum(1 for r in results if r["status"] == "ok")
    total = len(results)

    rows = ["| Pos | URL | Status | Reason |",
            "|-----|-----|--------|--------|"]
    for r in results:
        url_s = r["url"][:70] + ("…" if len(r["url"]) > 70 else "")
        status_word = "ok" if r["status"] == "ok" else "failed"
        reason = "—" if r["status"] == "ok" else r["status"]
        rows.append(f"| {r['pos']:3d} | {url_s} | {status_word} | {reason} |")

    lines = [
        f"# Raw Mode Scrape — Q{query_id}: {query_text}",
        "",
        f"**Source:** `{input_path}`",
        f"**URLs:** {total}",
        f"**Successes:** {ok_count} / {total}",
        f"**Runtime:** {runtime:.0f}s",
        "",
        *rows,
    ]

    report_path = out_dir / "02_raw_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="Mode 1 raw scrape: Crawl4AI direct, no prod deps, all URLs parallel via arun_many."
    )
    parser.add_argument("--input", required=True, help="Path to search smoke report MD file")
    parser.add_argument("--query", type=int, default=24, help="Query number (default: 24)")
    parser.add_argument(
        "--output-dir", dest="output_dir", default=None,
        help="Output directory (default: dev/scrape_pipeline/02_raw_data/<timestamp>/)"
    )
    args = parser.parse_args()
    asyncio.run(raw_smoke_workflow(args.input, args.query, args.output_dir))


if __name__ == "__main__":
    main()
