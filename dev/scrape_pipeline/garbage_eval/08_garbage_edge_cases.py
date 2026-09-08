#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from src.crawler.garbage_filter import is_garbage_content

REPORTS_DIR = Path(__file__).parent / "md"
EDGE_CASES = {
    "consent_prefix": [
        "https://www.azubiyo.de/bewerbung/layout/",
        "https://www.stepstone.de/magazin/bewerbung/",
    ],
    "padded_404": [
        "https://medium.com/nonexistent-article-xyz-12345",
        "https://dev.to/nonexistent-user-xyz/nonexistent-post-12345",
    ],
    "baseline_good": [
        "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "https://docs.python.org/3/tutorial/",
    ],
}


# ORCHESTRATOR
async def run_edge_case_suite():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"08_garbage_edge_cases_{timestamp}.md"

    sections = ["# Garbage Detection Edge Cases\n"]

    all_urls = [(cat, url) for cat, urls in EDGE_CASES.items() for url in urls]
    for i, (category, url) in enumerate(all_urls):
        print(f"Testing [{category}]: {url}")
        section = await test_url(category, url)
        sections.append(section)
        if i < len(all_urls) - 1:
            await asyncio.sleep(3)

    report_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"Report: {report_path}")


# FUNCTIONS

# Scrape URL with and without filter, run garbage detection
async def test_url(category: str, url: str) -> str:
    markdown_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48)
    )
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=markdown_generator,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    raw = result.markdown.raw_markdown if result.markdown and result.markdown.raw_markdown else ""
    filtered = result.markdown.fit_markdown if result.markdown and result.markdown.fit_markdown else ""

    return format_url_section(category, url, raw, filtered)


# Format one URL result as markdown section under its category
def format_url_section(category: str, url: str, raw: str, filtered: str) -> str:
    raw_result = is_garbage_content(raw) if raw else "NO CONTENT"
    filtered_result = is_garbage_content(filtered) if filtered else "NO CONTENT"
    raw_preview = raw[:300].replace("\n", " ") if raw else ""
    filtered_preview = filtered[:300].replace("\n", " ") if filtered else ""

    lines = [f"\n## Category: {category}\n", f"### URL: {url}\n"]
    lines.append(f"- Raw content: {len(raw)} chars")
    lines.append(f"- First 300 chars: `{raw_preview}`")
    lines.append(f"- Filtered content: {len(filtered)} chars")
    lines.append(f"- First 300 chars: `{filtered_preview}`")
    lines.append(f"- is_garbage(raw): {raw_result}")
    lines.append(f"- is_garbage(filtered): {filtered_result}")

    if category == "padded_404":
        header_zone = raw[:500] if raw else ""
        header_result = is_garbage_content(header_zone) if header_zone else "NO CONTENT"
        lines.append(f"- is_garbage(first_500_chars): {header_result}  ← header-zone test")

    assessment = assess_result(category, raw_result, filtered_result)
    lines.append(f"- Assessment: {assessment}")

    return "\n".join(lines)


# Determine whether garbage detection behaved correctly for this category
def assess_result(category: str, raw_result, filtered_result) -> str:
    if category == "baseline_good":
        if raw_result is None and filtered_result is None:
            return "correctly detected (no garbage)"
        return f"false positive — raw={raw_result}, filtered={filtered_result}"

    if category == "consent_prefix":
        if raw_result is None and filtered_result is None:
            return "garbage missed — consent prefix not detected"
        return f"correctly detected — {raw_result or filtered_result}"

    if category == "padded_404":
        if raw_result is None and filtered_result is None:
            return "garbage missed — padded 404 not detected"
        return f"correctly detected — {raw_result or filtered_result}"

    return "unknown category"


if __name__ == "__main__":
    asyncio.run(run_edge_case_suite())
