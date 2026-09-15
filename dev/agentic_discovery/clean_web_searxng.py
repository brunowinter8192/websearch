#!/usr/bin/env python3
"""
Cleanup script for website-crawled markdown files in:
  ~/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng/

Processes 2076 files from 12 domain prefixes (searxng, crawl4ai, playwright,
tor, anthropic, trafilatura, onetrust, cookieyes, web, paper, sitemaps, cookiebot).

Strategy per domain:
- Header: everything before the first real # heading
- Footer: domain-specific markers
- Inline: [docs][](URL) markers in source-code files

Files are overwritten in-place. <!-- source: URL --> comments are preserved.
"""

import re
import sys
from pathlib import Path

INPUT_DIR = Path.home() / "Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng"

# ------------------------------------------------------------------
# Inline noise patterns (apply to all files)
# ------------------------------------------------------------------
INLINE_DOCS_MARKER = re.compile(r'\[docs\]\[\]\(https?://[^)]*\)\n?')

# ------------------------------------------------------------------
# Footer marker patterns per domain prefix
# Each is a compiled regex that matches the START of the footer block.
# Everything from that line onwards (inclusive) is removed.
# ------------------------------------------------------------------

# SearXNG Sphinx docs: footer starts with logo image line
SEARXNG_FOOTER = re.compile(r'^\[ !\[Logo of SearXNG\]', re.MULTILINE)

# Crawl4AI MkDocs: footer starts with "Page Copy" or "ESC to close" or
# the duplicated TOC after content ends
CRAWL4AI_FOOTER = re.compile(
    r'^(?:Page Copy\s*$|ESC to close\s*$)',
    re.MULTILINE
)

# Playwright Docusaurus: footer starts with "[Previous " navigation
PLAYWRIGHT_FOOTER = re.compile(
    r'^\[Previous\s',
    re.MULTILINE
)

# Tor Project: footer starts with "[Edit this page]"
TOR_FOOTER = re.compile(
    r'^\[Edit this page\]\(',
    re.MULTILINE
)

# Anthropic docs: footer starts with "### Solutions" or "### Partners" etc.
# (nav link sections). Also catch the icon-only link lines like [](https://platform...)
# that appear just before the nav sections.
ANTHROPIC_FOOTER = re.compile(
    r'^(?:\[\]\(https://(?:platform\.claude\.com|x\.com|www\.linkedin\.com|instagram\.com)|### (?:Solutions|Partners|Company|Learn|Help and security|Terms and policies))\s*',
    re.MULTILINE
)

# Trafilatura ReadTheDocs (Sphinx): logo image line OR copyright line
TRAFILATURA_FOOTER = re.compile(
    r'^(?:\[ !\[Trafilatura|© Copyright \d{4})',
    re.MULTILINE
)

# OneTrust: footer starts with "Getting Started" nav section after content,
# or "Did this page help you?" widget
ONETRUST_FOOTER = re.compile(
    r'^(?:Getting Started|Did this page help you\?)\s*$',
    re.MULTILINE
)

# CookieYes: footer starts with "## Have more questions?" or "## CookieYes" nav block
COOKIEYES_FOOTER = re.compile(
    r'^## (?:Have more questions\?|CookieYes)\s*$',
    re.MULTILINE
)

# Generic: copyright line (fallback for misc domains)
GENERIC_COPYRIGHT = re.compile(
    r'^(?:Copyright ©|© Copyright|© \d{4})',
    re.MULTILINE
)

# ------------------------------------------------------------------
# Header detection: find the first real # heading line
# Everything before it is considered navigation noise EXCEPT the
# <!-- source: URL --> comment which we preserve.
# ------------------------------------------------------------------

SOURCE_COMMENT = re.compile(r'^<!-- source:.*?-->\s*\n?', re.MULTILINE)
FIRST_H1 = re.compile(r'^# .+', re.MULTILINE)


def extract_source_comment(text: str) -> tuple[str, str]:
    """Return (source_comment_text, remaining_text)."""
    m = SOURCE_COMMENT.match(text)
    if m:
        return m.group(0), text[m.end():]
    return "", text


def find_content_start(text: str) -> int:
    """Return the character index of the first # heading line."""
    m = FIRST_H1.search(text)
    if m:
        return m.start()
    return 0  # No heading found, keep everything


def get_domain_prefix(filename: str) -> str:
    """Extract domain prefix from filename like 'crawl4ai__...'."""
    return filename.split("__")[0]


def remove_footer(text: str, prefix: str) -> str:
    """Remove footer based on domain prefix."""
    pattern_map = {
        "searxng": SEARXNG_FOOTER,
        "trafilatura": TRAFILATURA_FOOTER,
        "crawl4ai": CRAWL4AI_FOOTER,
        "playwright": PLAYWRIGHT_FOOTER,
        "tor": TOR_FOOTER,
        "anthropic": ANTHROPIC_FOOTER,
        "onetrust": ONETRUST_FOOTER,
        "cookieyes": COOKIEYES_FOOTER,
    }

    pattern = pattern_map.get(prefix)
    if pattern:
        m = pattern.search(text)
        if m:
            return text[:m.start()].rstrip()
    else:
        # Generic fallback: try copyright line
        m = GENERIC_COPYRIGHT.search(text)
        if m:
            return text[:m.start()].rstrip()

    return text


# Additional UI noise patterns (apply after main content extraction)
COPY_PAGE_LINE = re.compile(r'^Copy page\s*$', re.MULTILINE)
WAS_PAGE_HELPFUL = re.compile(r'^Was this page helpful\?\s*$', re.MULTILINE)
# Trailing TOC-only anchor list (lines like "  * [Title](#anchor)")
# appearing after "Was this page helpful?" — handled by WAS_PAGE_HELPFUL cutoff
# "On this page" sidebar marker in some docs
ON_THIS_PAGE = re.compile(r'^On this page\s*$', re.MULTILINE)

# Search bar artifacts
SEARCH_BAR = re.compile(r'^Search\s*`[^`]+`\s*`[^`]+`\s*$', re.MULTILINE)


def remove_inline_markers(text: str) -> str:
    """Remove [docs][](URL) inline markers from source code files."""
    text = INLINE_DOCS_MARKER.sub('', text)
    return text


def remove_ui_noise(text: str) -> str:
    """Remove inline UI chrome that appears within content."""
    # Remove "Copy page" lines (Anthropic docs UI button)
    text = COPY_PAGE_LINE.sub('', text)
    # Cut at "Was this page helpful?" (anthropic docs footer widget)
    m = WAS_PAGE_HELPFUL.search(text)
    if m:
        text = text[:m.start()].rstrip()
    return text


def clean_file(path: Path) -> tuple[int, int]:
    """
    Clean a single file in-place.
    Returns (chars_before, chars_after).
    """
    original = path.read_text(encoding="utf-8", errors="replace")
    chars_before = len(original)

    prefix = get_domain_prefix(path.name)

    # 1. Extract and preserve <!-- source: URL --> comment
    source_comment, rest = extract_source_comment(original)

    # 2. Find content start (first # heading)
    content_start = find_content_start(rest)
    content = rest[content_start:]

    # 3. Remove footer
    content = remove_footer(content, prefix)

    # 4. Remove inline [docs][](URL) markers
    content = remove_inline_markers(content)

    # 4b. Remove UI noise within content (Copy page, Was this page helpful, etc.)
    content = remove_ui_noise(content)

    # 5. Clean up excessive blank lines (max 2 consecutive)
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()

    # 6. Reassemble
    if source_comment:
        cleaned = source_comment + "\n" + content + "\n"
    else:
        cleaned = content + "\n"

    chars_after = len(cleaned)

    if cleaned != original:
        path.write_text(cleaned, encoding="utf-8")

    return chars_before, chars_after


def _process_files(files: list, test_file: str | None) -> tuple[int, int, int, int, dict]:
    total_before = 0
    total_after = 0
    processed = 0
    skipped = 0

    # Count by prefix for reporting
    prefix_counts: dict[str, int] = {}

    for path in files:
        if test_file and path.name != test_file:
            continue

        prefix = get_domain_prefix(path.name)
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

        try:
            before, after = clean_file(path)
            total_before += before
            total_after += after
            processed += 1
        except Exception as e:
            print(f"  ERROR {path.name}: {e}")
            skipped += 1

    return total_before, total_after, processed, skipped, prefix_counts


def _print_report(processed: int, skipped: int, prefix_counts: dict, total_before: int,
                   total_after: int, reduction: float) -> None:
    print(f"\nFILES PROCESSED: {processed} (skipped: {skipped})")
    print(f"\nPATTERNS DETECTED:")
    for prefix, count in sorted(prefix_counts.items()):
        print(f"  - {prefix}: {count} files")
    print(f"\nCLEANUP RESULTS:")
    print(f"  Total chars before: {total_before:,}")
    print(f"  Total chars after:  {total_after:,}")
    print(f"  Reduction:          {reduction:.1f}%")
    print(f"\nSCRIPT: dev/agentic_discovery/clean_web_searxng.py")
    print(f"OUTPUT: in-place (originals overwritten)")


def main():
    if not INPUT_DIR.exists():
        print(f"ERROR: Input directory not found: {INPUT_DIR}")
        sys.exit(1)

    files = sorted(INPUT_DIR.glob("*.md"))
    if not files:
        print("No .md files found.")
        sys.exit(0)

    # Allow single-file test mode
    test_file = None
    if len(sys.argv) > 1:
        test_file = sys.argv[1]

    total_before, total_after, processed, skipped, prefix_counts = _process_files(files, test_file)

    reduction = (1 - total_after / total_before) * 100 if total_before else 0

    _print_report(processed, skipped, prefix_counts, total_before, total_after, reduction)


if __name__ == "__main__":
    main()
