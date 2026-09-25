#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

REPORTS_DIR = Path(__file__).parent / "md"
HTTP_FIELDS = ["status_code", "http_status", "status", "success", "error_message", "response_headers", "metadata"]
TEST_URLS = [
    ("normal", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ("404", "https://medium.com/nonexistent-article-xyz-12345"),
    ("consent", "https://www.azubiyo.de/bewerbung/layout/"),
]


# ORCHESTRATOR

async def run_result_inspection():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = _compute_report_path(timestamp)

    sections = ["# Crawl4AI Result Object Inspection\n"]

    await _inspect_urls(sections)

    report_path.write_text("\n".join(sections), encoding="utf-8")
    _print_report(report_path)


# FUNCTIONS

def _compute_report_path(timestamp):
    report_path = REPORTS_DIR / f"07_result_inspect_{timestamp}.md"
    return report_path


async def _inspect_urls(sections):
    for i, (label, url) in enumerate(TEST_URLS):
        print(f"Inspecting [{label}]: {url}")
        section = await inspect_url(label, url)
        sections.append(section)
        if i < len(TEST_URLS) - 1:
            await asyncio.sleep(2)


def _print_report(report_path):
    print(f"Report: {report_path}")


async def inspect_url(label: str, url: str) -> str:
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_until="networkidle")

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    attr_rows = build_attribute_table(result)
    http_fields = build_http_section(result)
    return format_url_section(label, url, attr_rows, http_fields)


def build_attribute_table(result) -> list[tuple]:
    rows = []
    for attr in sorted(a for a in dir(result) if not a.startswith("_")):
        try:
            val = getattr(result, attr)
            if callable(val):
                continue
            val_str = repr(val)[:200]
            val_type = type(val).__name__
            rows.append((attr, val_type, val_str))
        except Exception as e:
            rows.append((attr, "ERROR", str(e)[:200]))
    return rows


def build_http_section(result) -> dict:
    findings = {}
    for field in HTTP_FIELDS:
        if hasattr(result, field):
            try:
                val = getattr(result, field)
                findings[field] = f"EXISTS — value: {repr(val)[:300]}"
            except Exception as e:
                findings[field] = f"ERROR: {e}"
        else:
            findings[field] = "MISSING"
    return findings


def format_url_section(label: str, url: str, attr_rows: list[tuple], http_fields: dict) -> str:
    lines = [f"\n## [{label}] URL: {url}\n"]

    lines.append("### All Attributes\n")
    lines.append("| Attribute | Type | Value (truncated) |")
    lines.append("|-----------|------|-------------------|")
    for attr, val_type, val_str in attr_rows:
        escaped = val_str.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{attr}` | {val_type} | {escaped} |")

    lines.append("\n### HTTP-Relevant Fields\n")
    for field, info in http_fields.items():
        lines.append(f"- **{field}**: {info}")

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(run_result_inspection())
