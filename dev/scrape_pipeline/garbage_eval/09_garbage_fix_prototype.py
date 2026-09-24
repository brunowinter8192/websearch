#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

REPORTS_DIR = Path(__file__).parent / "md"
CONSENT_WORDS = ["cookie", "consent", "einwilligung", "tracking", "akzeptieren", "datenschutz", "zweck"]
CONSENT_DENSITY_THRESHOLD = 5
CONSENT_SKIP_OFFSET = 300

FIX1_URLS = [
    ("padded_404", "https://medium.com/nonexistent-article-xyz-12345"),
    ("padded_404", "https://dev.to/nonexistent-user-xyz/nonexistent-post-12345"),
    ("baseline", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ("baseline", "https://www.azubiyo.de/bewerbung/layout/"),
]

FIX2_URLS = [
    ("consent_prefix", "https://www.azubiyo.de/bewerbung/layout/"),
    ("consent_prefix", "https://www.stepstone.de/magazin/bewerbung/"),
    ("baseline", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ("baseline", "https://docs.python.org/3/tutorial/"),
]


# ORCHESTRATOR
async def run_fix_prototype():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"09_garbage_fix_prototype_{timestamp}.md"

    all_urls = list(dict.fromkeys(url for _, url in FIX1_URLS + FIX2_URLS))
    print(f"Scraping {len(all_urls)} unique URLs...")
    results = await scrape_all_urls(all_urls)

    fix1_section = build_fix1_section(results)
    fix2_section = build_fix2_section(results)
    recommendation = build_recommendation(results)

    report = "\n\n".join(["# Garbage Detection Fix Prototypes", fix1_section, fix2_section, recommendation])
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}")


# FUNCTIONS

async def scrape_all_urls(urls: list[str]) -> dict:
    markdown_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48)
    )
    browser_config = BrowserConfig(headless=True, verbose=False)
    results = {}

    for i, url in enumerate(urls):
        print(f"  [{i+1}/{len(urls)}] {url}")
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="networkidle",
            markdown_generator=markdown_generator,
        )
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
        results[url] = result
        if i < len(urls) - 1:
            await asyncio.sleep(3)

    return results


def build_fix1_section(results: dict) -> str:
    lines = ["## Fix 1: status_code based 404 detection\n"]
    lines.append("| URL | status_code | Would trigger http_error? | Correct? |")
    lines.append("|-----|-------------|---------------------------|----------|")

    for category, url in FIX1_URLS:
        result = results.get(url)
        status = getattr(result, "status_code", None) if result else None
        triggers = status is not None and status >= 400

        if category == "padded_404":
            correct = "YES ✅" if triggers else "NO ❌"
        else:
            correct = "YES ✅" if not triggers else "FALSE POSITIVE ❌"

        short_url = url.replace("https://", "")[:65]
        lines.append(f"| {short_url} | {status} | {'YES' if triggers else 'NO'} | {correct} |")

    return "\n".join(lines)


def build_fix2_section(results: dict) -> str:
    lines = ["## Fix 2: consent prefix stripping\n"]

    for category, url in FIX2_URLS:
        result = results.get(url)
        raw = result.markdown.raw_markdown if result and result.markdown and result.markdown.raw_markdown else ""
        stripped = strip_consent_prefix(raw)
        chars_removed = len(raw) - len(stripped)

        heading_match = re.match(r'#{1,2} .+', stripped[:300])
        heading_start = heading_match.group(0)[:80] if heading_match else "(no heading found at start)"

        if category == "baseline":
            if chars_removed == 0:
                assessment = "nothing removed ✅"
            else:
                assessment = f"PROBLEM: removed {chars_removed} chars ❌"
        elif chars_removed > 200:
            assessment = f"effective — removed {chars_removed} chars ✅"
        elif chars_removed > 0:
            assessment = f"partial — removed only {chars_removed} chars ⚠️"
        else:
            assessment = "not effective — nothing removed ❌"

        short_label = url.replace("https://www.", "").replace("https://", "")[:50]
        lines.append(f"### {short_label}\n")
        lines.append(f"- Original first 200 chars: `{raw[:200].replace(chr(10), ' ')}`")
        lines.append(f"- Stripped first 200 chars: `{stripped[:200].replace(chr(10), ' ')}`")
        lines.append(f"- Chars removed: {chars_removed}")
        lines.append(f"- Content starts at heading: `{heading_start}`")
        lines.append(f"- Assessment: {assessment}\n")

    return "\n".join(lines)


def strip_consent_prefix(content: str) -> str:
    if not content:
        return content
    sample = content[:3000].lower()
    density = sum(sample.count(w) for w in CONSENT_WORDS)
    if density <= CONSENT_DENSITY_THRESHOLD:
        return content
    match = re.search(r'\n(#{1,2} )', content[CONSENT_SKIP_OFFSET:])
    if match:
        pos = CONSENT_SKIP_OFFSET + match.start() + 1
        return content[pos:]
    return content


def build_recommendation(results: dict) -> str:
    medium_url = "https://medium.com/nonexistent-article-xyz-12345"
    wiki_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    azubiyo_url = "https://www.azubiyo.de/bewerbung/layout/"

    medium_status = getattr(results.get(medium_url), "status_code", None)
    wiki_status = getattr(results.get(wiki_url), "status_code", None)
    fix1_catches_404 = medium_status is not None and medium_status >= 400
    fix1_no_false_positive = wiki_status is None or wiki_status < 400
    fix1_ready = fix1_catches_404 and fix1_no_false_positive

    azubiyo_result = results.get(azubiyo_url)
    azubiyo_raw = azubiyo_result.markdown.raw_markdown if azubiyo_result and azubiyo_result.markdown and azubiyo_result.markdown.raw_markdown else ""
    stripped = strip_consent_prefix(azubiyo_raw)
    fix2_effective = len(azubiyo_raw) - len(stripped) > 200

    lines = ["## Recommendation\n"]

    if fix1_ready:
        lines.append(
            "**Fix 1 (status_code >= 400): Production-ready.** "
            "Check `result.status_code` before content analysis in `try_scrape()`. "
            "If >= 400, return `(\"\" , \"http_error\")` immediately — eliminates content-length "
            "dependency and catches padded error pages regardless of body size."
        )
    else:
        lines.append(
            f"**Fix 1 (status_code): NOT ready.** "
            f"medium.com status={medium_status}, wiki status={wiki_status}. Needs investigation."
        )

    lines.append("")

    if fix2_effective:
        lines.append(
            "**Fix 2 (consent prefix strip): Prototype shows promise for azubiyo-style sites.** "
            "Requires integration into `try_scrape()` as a post-processing step before `is_garbage_content()`. "
            "Stepstone is a nav-dump, not a consent-prefix — different problem. "
            "Not yet production-ready: threshold and heading-search need broader site testing."
        )
    else:
        lines.append(
            "**Fix 2 (consent prefix strip): Not effective enough.** "
            f"Removed <= 200 chars from azubiyo. "
            "Consider CSS excluded_selector approach or stricter density scan window."
        )

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(run_fix_prototype())
