#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    PruningContentFilter,
    BM25ContentFilter,
)
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

DESCRIPTION = """
sweep.py — Crawl4AI filter sweep against Q24 URLs.

Iterates filter × content_source × excluded_selector combos defined in
sweep_config.yml. Saves one .md per (config, URL). Writes _run_metadata.json
with timing + size info for analyzer.

NO prod imports. NO cli.py subprocess. Crawl4AI directly via arun_many.

Usage:
    ./venv/bin/python dev/scrape_pipeline/04_overview_sweep/sweep.py
    ./venv/bin/python dev/scrape_pipeline/04_overview_sweep/sweep.py --config <path>
    ./venv/bin/python dev/scrape_pipeline/04_overview_sweep/sweep.py --output-dir <path>
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "dev" / "scrape_pipeline" / "04_overview_sweep" / "sweep_config.yml"
OUTPUT_BASE = PROJECT_ROOT / "dev" / "scrape_pipeline" / "04_overview_sweep" / "sweep_data"

QUERY_SECTION_RE = re.compile(r"^## Q(\d+): (.+)$")
ENTRY_RE = re.compile(r"^(\d+)\. \*\*\[([A-Z?]+)\]\*\*")
URL_LINE_RE = re.compile(r"^\s+URL: (https?://\S+)$")


async def sweep_workflow(config_path: Path, output_dir: Path) -> None:
    sweep_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    smoke_report = PROJECT_ROOT / sweep_cfg["input"]["smoke_report"]
    query_id = sweep_cfg["input"]["query_id"]

    query_text, urls = parse_q_urls(smoke_report, query_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    combos = list(generate_combos(sweep_cfg))
    print(f"sweep: {len(urls)} URLs × {len(combos)} configs = {len(urls)*len(combos)} outputs", file=sys.stderr)
    print(f"output: {output_dir}\n", file=sys.stderr)

    browser_config = BrowserConfig(headless=True, verbose=False)
    metadata = build_initial_metadata(query_id, query_text, urls, combos)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, combo in enumerate(combos, 1):
            config_entry = await run_one_combo(crawler, combo, i, len(combos), urls, output_dir)
            metadata["configs"].append(config_entry)

    metadata["finished"] = datetime.now().isoformat(timespec="seconds")
    (output_dir / "_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\nDone. Metadata: {output_dir}/_run_metadata.json", file=sys.stderr)


def build_initial_metadata(query_id: int, query_text: str, urls: list, combos: list) -> dict:
    return {
        "started": datetime.now().isoformat(timespec="seconds"),
        "query_id": query_id,
        "query_text": query_text,
        "url_count": len(urls),
        "config_count": len(combos),
        "configs": [],
    }


async def run_one_combo(crawler, combo: dict, index: int, total: int, urls: list, output_dir: Path) -> dict:
    config_name = combo["name"]
    config_dir = output_dir / config_name
    config_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{index:02d}/{total}] {config_name}", file=sys.stderr)
    t0 = time.time()
    run_config = build_run_config(combo)
    try:
        results = await crawler.arun_many(urls=urls, config=run_config)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"    EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr)
        return {
            "name": config_name, "filter": combo["filter"], "content_source": combo["content_source"],
            "selector": combo["selector"], "elapsed_seconds": round(elapsed, 1),
            "exception": f"{type(e).__name__}: {e}", "outputs": [],
        }
    elapsed = time.time() - t0

    outputs = save_combo_outputs(combo, results, urls, config_dir)
    success_count = sum(1 for o in outputs if o["status"] == "ok")
    print(f"    {success_count}/{len(urls)} ok in {elapsed:.0f}s", file=sys.stderr)
    return {
        "name": config_name,
        "filter": combo["filter"],
        "content_source": combo["content_source"],
        "selector": combo["selector"],
        "elapsed_seconds": round(elapsed, 1),
        "outputs": outputs,
    }


def generate_combos(sweep_cfg: dict):
    for f in sweep_cfg["filters"]:
        for cs in sweep_cfg["content_sources"]:
            for sel in sweep_cfg["excluded_selectors"]:
                yield {
                    "name": f"{f['name']}_{cs}_{sel['name']}",
                    "filter": f,
                    "content_source": cs,
                    "selector": sel,
                }


def build_run_config(combo: dict) -> CrawlerRunConfig:
    f = combo["filter"]
    cs = combo["content_source"]
    sel = combo["selector"]

    if f["type"] == "none":
        content_filter = None
    elif f["type"] == "pruning":
        content_filter = PruningContentFilter(threshold=f["threshold"])
    elif f["type"] == "bm25":
        content_filter = BM25ContentFilter(user_query=f["user_query"])
    else:
        raise ValueError(f"Unknown filter type: {f['type']}")

    markdown_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        content_source=cs,
    )

    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        excluded_selector=sel["value"],
        markdown_generator=markdown_generator,
    )


def save_combo_outputs(combo: dict, results: list, urls: list, config_dir: Path) -> list:
    has_filter = combo["filter"]["type"] != "none"
    result_by_url = {r.url: r for r in results}
    outputs = []

    for url in urls:
        r = result_by_url.get(url)
        if r is None:
            outputs.append({"url": url, "status": "exception: missing_from_results", "filename": None, "bytes": 0})
            continue

        try:
            if r.markdown is None:
                outputs.append({"url": url, "status": "empty: no_markdown_object", "filename": None, "bytes": 0})
                continue

            content = r.markdown.fit_markdown if has_filter else r.markdown.raw_markdown
            if not content:
                hint = empty_hint(url)
                outputs.append({"url": url, "status": f"empty{hint}", "filename": None, "bytes": 0})
                continue
        except Exception as e:
            outputs.append({"url": url, "status": f"exception: {type(e).__name__}", "filename": None, "bytes": 0})
            continue

        filename = sanitize_filename(url) + ".md"
        filepath = config_dir / filename
        body = f"<!-- source: {url} -->\n\n{content}"
        filepath.write_text(body, encoding="utf-8")
        outputs.append({"url": url, "status": "ok", "filename": filename, "bytes": len(body)})

    return outputs


def empty_hint(url: str) -> str:
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext == ".pdf":
        return " (PDF)"
    domain = url.split("/")[2] if "//" in url else ""
    plugin_domains = ("github.com", "arxiv.org", "reddit.com")
    for d in plugin_domains:
        if d in domain:
            return f" (plugin-domain: {d.split('.')[0]})"
    return ""


def sanitize_filename(url: str) -> str:
    slug = re.sub(r"[^\w]", "_", url)[:80]
    h = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{slug}_{h}"


def parse_q_urls(smoke_report: Path, query_id: int) -> tuple[str, list]:
    lines = smoke_report.read_text(encoding="utf-8").splitlines()
    q_text, start, end = find_query_section(lines, query_id)
    urls = extract_urls(lines, start, end)
    return q_text, urls


def find_query_section(lines: list, query_id: int) -> tuple[str, int, int]:
    start = -1
    q_text = ""
    for i, line in enumerate(lines):
        m = QUERY_SECTION_RE.match(line)
        if not m:
            continue
        if int(m.group(1)) == query_id:
            start = i
            q_text = m.group(2)
        elif start != -1:
            return q_text, start, i
    if start == -1:
        raise ValueError(f"Query Q{query_id} not found in smoke report")
    return q_text, start, len(lines)


def extract_urls(lines: list, start: int, end: int) -> list:
    urls = []
    in_entry = False
    for line in lines[start:end]:
        if ENTRY_RE.match(line):
            in_entry = True
            continue
        if in_entry:
            m = URL_LINE_RE.match(line)
            if m:
                urls.append(m.group(1))
                in_entry = False
    return urls


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to sweep_config.yml")
    parser.add_argument("--output-dir", default=None, help="Output dir (default: sweep_data/<timestamp>/)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = OUTPUT_BASE / ts

    asyncio.run(sweep_workflow(config_path, output_dir))


if __name__ == "__main__":
    main()
