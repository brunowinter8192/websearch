#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.scraper.routing import resolve_profile, load_config, match_url_to_profile
from src.scraper.html_parser import parse_html
from src.scraper.content_filter import (
    remove_skip_tags,
    extract_main_content,
    remove_navigation_attributes,
    remove_skip_tables,
    remove_noise_links,
    remove_noise_text,
)
from src.scraper.markdown_converter import (
    convert_nodes_to_markdown,
    clean_markdown_artifacts,
    clean_generic_artifacts,
    clean_whitespace,
)
from src.scraper.chromium_scrape import init_browser, fetch_url_content, cleanup_browser

REPORT_DIR = Path(__file__).parent / "md"
DOMAINS_FILE = Path(__file__).parent.parent / "domains.txt"
MAX_PREVIEW_CHARS = 500


# ORCHESTRATOR
async def filter_debug_suite(urls: list[str]):
    browser = await init_browser()

    for url in urls:
        profile = resolve_profile(url)
        profile_name = resolve_profile_name(url)
        print(f"\nFetching: {url}")
        raw_html = await fetch_url_content(url, browser, profile)

        if isinstance(raw_html, Exception):
            print(f"  FAILED: {raw_html}")
            continue

        report = run_pipeline_debug(url, raw_html, profile, profile_name)
        print_console_summary(report)
        save_report(report)

    await cleanup_browser(browser)
    print(f"\nDone. Reports in: {REPORT_DIR}/")


# FUNCTIONS

# Resolve profile name string for display and folder naming
def resolve_profile_name(url: str) -> str:
    config = load_config()
    return match_url_to_profile(url, config.get("routing", {}))


# Run pipeline step-by-step and capture intermediate state
def run_pipeline_debug(url: str, raw_html: str, profile: dict, profile_name: str) -> dict:
    parsed = parse_html(raw_html)
    nodes = parsed.get("nodes", [])

    steps, after_text = run_node_level_filter_steps(nodes, profile)
    raw_md = convert_nodes_to_markdown(after_text)
    md_steps, after_whitespace = run_markdown_cleanup_steps(raw_md, profile)

    return {
        "url": url,
        "profile_name": profile_name,
        "profile_config": profile,
        "timestamp": datetime.now().isoformat(),
        "html_length": len(raw_html),
        "filter_steps": steps,
        "markdown_steps": md_steps,
        "final_chars": len(after_whitespace),
        "raw_markdown": raw_md,
        "clean_markdown": after_whitespace,
    }


def run_node_level_filter_steps(nodes: list, profile: dict) -> tuple[list, list]:
    steps = []
    steps.append(make_step("parse_html", None, nodes))

    after_skip = remove_skip_tags(nodes)
    steps.append(make_step("remove_skip_tags", nodes, after_skip))

    after_main = extract_main_content(after_skip)
    steps.append(make_step("extract_main_content", after_skip, after_main))

    nav_patterns = profile.get("nav_patterns", [])
    after_nav = remove_navigation_attributes(after_main, nav_patterns)
    steps.append(make_step("remove_nav_attributes", after_main, after_nav, config=nav_patterns))

    skip_classes = profile.get("skip_table_classes", [])
    if skip_classes:
        after_tables = remove_skip_tables(after_nav, skip_classes)
    else:
        after_tables = after_nav
    steps.append(make_step("remove_skip_tables", after_nav, after_tables, config=skip_classes))

    noise_urls = profile.get("noise_url_patterns", [])
    if noise_urls:
        after_links = remove_noise_links(after_tables, noise_urls)
    else:
        after_links = after_tables
    steps.append(make_step("remove_noise_links", after_tables, after_links, config=noise_urls))

    noise_text = profile.get("noise_text_patterns", [])
    if noise_text:
        after_text = remove_noise_text(after_links, noise_text)
    else:
        after_text = after_links
    steps.append(make_step("remove_noise_text", after_links, after_text, config=noise_text))

    return steps, after_text


def run_markdown_cleanup_steps(raw_md: str, profile: dict) -> tuple[list, str]:
    cleanup_tags = profile.get("markdown_cleanup", [])
    after_cleanup = clean_markdown_artifacts(raw_md, cleanup_tags)
    after_generic = clean_generic_artifacts(after_cleanup)
    after_whitespace = clean_whitespace(after_generic)

    md_steps = []
    md_steps.append({"name": "raw_markdown", "chars": len(raw_md), "delta_pct": None})
    md_steps.append(make_md_step("profile_cleanup", raw_md, after_cleanup, config=cleanup_tags))
    md_steps.append(make_md_step("generic_cleanup", after_cleanup, after_generic))
    md_steps.append(make_md_step("whitespace_clean", after_generic, after_whitespace))

    return md_steps, after_whitespace


# Build step dict for a node-level filter step
def make_step(name: str, before_nodes: list | None, after_nodes: list, config: list | None = None) -> dict:
    if before_nodes is None:
        return {
            "name": name,
            "nodes_before": None,
            "nodes_after": len(after_nodes),
            "chars_before": None,
            "chars_after": estimate_chars(after_nodes),
            "delta_pct": None,
            "removed_preview": None,
            "config": config,
        }

    chars_before = estimate_chars(before_nodes)
    chars_after = estimate_chars(after_nodes)
    delta_pct = ((chars_after - chars_before) / chars_before * 100) if chars_before > 0 else 0.0

    removed = diff_nodes(before_nodes, after_nodes)
    preview = nodes_to_preview(removed)

    return {
        "name": name,
        "nodes_before": len(before_nodes),
        "nodes_after": len(after_nodes),
        "chars_before": chars_before,
        "chars_after": chars_after,
        "delta_pct": delta_pct,
        "removed_preview": preview,
        "config": config,
    }


# Build step dict for a markdown-level cleanup step
def make_md_step(name: str, before: str, after: str, config: list | None = None) -> dict:
    delta_pct = ((len(after) - len(before)) / len(before) * 100) if len(before) > 0 else 0.0
    return {
        "name": name,
        "chars": len(after),
        "delta_pct": delta_pct,
        "config": config,
    }


# Estimate total text chars from node list
def estimate_chars(nodes: list) -> int:
    return sum(len(n.get("content", "")) for n in nodes if n.get("type") == "text")


# Find nodes present in before but not in after using index tracking
def diff_nodes(before: list, after: list) -> list:
    after_set = set(id(n) for n in after)
    return [n for n in before if id(n) not in after_set]


# Convert removed nodes to readable markdown preview
def nodes_to_preview(nodes: list) -> str:
    if not nodes:
        return ""
    try:
        preview_md = convert_nodes_to_markdown(nodes)
    except Exception:
        text_parts = [n.get("content", "") for n in nodes if n.get("type") == "text"]
        preview_md = " ".join(text_parts)
    return preview_md[:MAX_PREVIEW_CHARS * 4]


# Print compact console summary table
def print_console_summary(report: dict):
    url = report["url"]
    profile = report["profile_name"]

    print(f"\nPipeline Debug: {url}")
    print(f"Profile: {profile}")
    print(f"HTML: {report['html_length']} chars")
    print("=" * 60)
    print(f"{'Step':<28} {'Nodes':>8} {'Chars':>8} {'Delta':>8}")
    print("-" * 60)

    for step in report["filter_steps"]:
        name = step["name"]
        nodes = step["nodes_after"]
        chars = step["chars_after"]
        if step["delta_pct"] is None:
            delta = ""
        else:
            delta = f"{step['delta_pct']:+.1f}%"
        print(f"{name:<28} {nodes:>8} {chars:>8} {delta:>8}")

    print("-" * 60)

    for step in report["markdown_steps"]:
        name = step["name"]
        chars = step["chars"]
        if step["delta_pct"] is None:
            delta = ""
        else:
            delta = f"{step['delta_pct']:+.1f}%"
        print(f"{name:<28} {'':>8} {chars:>8} {delta:>8}")

    print("=" * 60)
    print(f"Final output: {report['final_chars']} chars")


# Save detailed report to file
def save_report(report: dict):
    profile = report["profile_name"]
    domain_name = extract_domain_name(report["url"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_dir = REPORT_DIR / profile
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"05_{domain_name}_{timestamp}.txt"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"FILTER DEBUG REPORT\n")
        f.write(f"URL: {report['url']}\n")
        f.write(f"Profile: {report['profile_name']}\n")
        f.write(f"Timestamp: {report['timestamp']}\n")
        f.write(f"HTML length: {report['html_length']}\n")
        f.write("=" * 80 + "\n\n")

        f.write("PROFILE CONFIG:\n")
        f.write("-" * 80 + "\n")
        for key, value in report["profile_config"].items():
            f.write(f"  {key}: {value}\n")
        f.write("\n")

        f.write("FILTER STEPS (Node-Level):\n")
        f.write("=" * 80 + "\n")
        for step in report["filter_steps"]:
            write_filter_step(f, step)

        f.write("\nMARKDOWN STEPS:\n")
        f.write("=" * 80 + "\n")
        for step in report["markdown_steps"]:
            write_markdown_step(f, step)

        f.write(f"\nFINAL OUTPUT: {report['final_chars']} chars\n")

    raw_file = report_dir / f"05_{domain_name}_{timestamp}_raw.md"
    clean_file = report_dir / f"05_{domain_name}_{timestamp}_clean.md"

    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(report["raw_markdown"])

    with open(clean_file, "w", encoding="utf-8") as f:
        f.write(report["clean_markdown"])

    print(f"  Report: {report_file}")
    print(f"  Raw MD: {raw_file}")
    print(f"  Clean MD: {clean_file}")


# Write single filter step detail to report file
def write_filter_step(f, step: dict):
    f.write(f"\n=== STEP: {step['name']} ===\n")

    if step["nodes_before"] is None:
        f.write(f"Nodes: {step['nodes_after']}\n")
        f.write(f"Chars (text): {step['chars_after']}\n")
    else:
        node_diff = step["nodes_after"] - step["nodes_before"]
        char_diff = step["chars_after"] - step["chars_before"]
        delta = f"{step['delta_pct']:+.1f}%" if step["delta_pct"] is not None else ""
        f.write(f"Nodes: {step['nodes_before']} -> {step['nodes_after']} ({node_diff:+d})\n")
        f.write(f"Chars: {step['chars_before']} -> {step['chars_after']} ({char_diff:+d}, {delta})\n")

    if step.get("config"):
        f.write(f"Config: {step['config']}\n")

    if step.get("removed_preview"):
        f.write(f"\nRemoved Content (Markdown Preview):\n")
        f.write("-" * 40 + "\n")
        f.write(step["removed_preview"])
        f.write("\n" + "-" * 40 + "\n")


# Write single markdown step detail to report file
def write_markdown_step(f, step: dict):
    f.write(f"\n--- {step['name']} ---\n")
    delta = f"{step['delta_pct']:+.1f}%" if step["delta_pct"] is not None else ""
    f.write(f"Chars: {step['chars']} ({delta})\n")
    if step.get("config"):
        f.write(f"Config: {step['config']}\n")


# Extract clean domain name from URL
def extract_domain_name(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]

    if "wikipedia.org" in parsed.netloc:
        return f"wikipedia_{path_parts[-1]}" if path_parts else "wikipedia"
    elif "searxng.org" in parsed.netloc:
        return "searxng_docs"
    elif "scikit-learn.org" in parsed.netloc:
        return "sklearn_docs"
    elif "medium.com" in parsed.netloc:
        return "medium_article"
    elif "trychroma.com" in parsed.netloc:
        return "chroma_docs"
    elif "binance.com" in parsed.netloc:
        return "binance_docs"
    else:
        return parsed.netloc.replace(".", "_")


# Load domains from domains.txt
def load_domains() -> list[str]:
    domains = []
    with open(DOMAINS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line)
    return domains


# Filter domains by profile name
def filter_domains_by_profile(domains: list[str], profile_name: str) -> list[str]:
    return [url for url in domains if resolve_profile_name(url) == profile_name]


# Parse CLI arguments
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter debug pipeline for scraping suite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs="?", help="Single URL to debug")
    group.add_argument("--profile", help="Run all domains matching this profile")
    group.add_argument("--all", action="store_true", help="Run all domains from domains.txt")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.url:
        urls = [args.url]
    elif args.profile:
        all_domains = load_domains()
        urls = filter_domains_by_profile(all_domains, args.profile)
        if not urls:
            print(f"No domains found for profile: {args.profile}")
            sys.exit(1)
        print(f"Profile '{args.profile}': {len(urls)} domain(s)")
    else:
        urls = load_domains()
        print(f"All domains: {len(urls)} domain(s)")

    asyncio.run(filter_debug_suite(urls))
