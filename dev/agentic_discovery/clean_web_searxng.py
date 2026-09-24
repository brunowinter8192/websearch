#!/usr/bin/env python3

import re
import sys
from pathlib import Path

INPUT_DIR = Path.home() / "Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng"

INLINE_DOCS_MARKER = re.compile(r'\[docs\]\[\]\(https?://[^)]*\)\n?')


SEARXNG_FOOTER = re.compile(r'^\[ !\[Logo of SearXNG\]', re.MULTILINE)

CRAWL4AI_FOOTER = re.compile(
    r'^(?:Page Copy\s*$|ESC to close\s*$)',
    re.MULTILINE
)

PLAYWRIGHT_FOOTER = re.compile(
    r'^\[Previous\s',
    re.MULTILINE
)

TOR_FOOTER = re.compile(
    r'^\[Edit this page\]\(',
    re.MULTILINE
)

ANTHROPIC_FOOTER = re.compile(
    r'^(?:\[\]\(https://(?:platform\.claude\.com|x\.com|www\.linkedin\.com|instagram\.com)|### (?:Solutions|Partners|Company|Learn|Help and security|Terms and policies))\s*',
    re.MULTILINE
)

TRAFILATURA_FOOTER = re.compile(
    r'^(?:\[ !\[Trafilatura|© Copyright \d{4})',
    re.MULTILINE
)

ONETRUST_FOOTER = re.compile(
    r'^(?:Getting Started|Did this page help you\?)\s*$',
    re.MULTILINE
)

COOKIEYES_FOOTER = re.compile(
    r'^## (?:Have more questions\?|CookieYes)\s*$',
    re.MULTILINE
)

GENERIC_COPYRIGHT = re.compile(
    r'^(?:Copyright ©|© Copyright|© \d{4})',
    re.MULTILINE
)


SOURCE_COMMENT = re.compile(r'^<!-- source:.*?-->\s*\n?', re.MULTILINE)
FIRST_H1 = re.compile(r'^# .+', re.MULTILINE)


def extract_source_comment(text: str) -> tuple[str, str]:
    m = SOURCE_COMMENT.match(text)
    if m:
        return m.group(0), text[m.end():]
    return "", text


def find_content_start(text: str) -> int:
    m = FIRST_H1.search(text)
    if m:
        return m.start()
    return 0


def get_domain_prefix(filename: str) -> str:
    return filename.split("__")[0]


def remove_footer(text: str, prefix: str) -> str:
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
        m = GENERIC_COPYRIGHT.search(text)
        if m:
            return text[:m.start()].rstrip()

    return text


COPY_PAGE_LINE = re.compile(r'^Copy page\s*$', re.MULTILINE)
WAS_PAGE_HELPFUL = re.compile(r'^Was this page helpful\?\s*$', re.MULTILINE)
ON_THIS_PAGE = re.compile(r'^On this page\s*$', re.MULTILINE)

SEARCH_BAR = re.compile(r'^Search\s*`[^`]+`\s*`[^`]+`\s*$', re.MULTILINE)


def remove_inline_markers(text: str) -> str:
    text = INLINE_DOCS_MARKER.sub('', text)
    return text


def remove_ui_noise(text: str) -> str:
    text = COPY_PAGE_LINE.sub('', text)
    m = WAS_PAGE_HELPFUL.search(text)
    if m:
        text = text[:m.start()].rstrip()
    return text


def clean_file(path: Path) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8", errors="replace")
    chars_before = len(original)

    prefix = get_domain_prefix(path.name)

    source_comment, rest = extract_source_comment(original)

    content_start = find_content_start(rest)
    content = rest[content_start:]

    content = remove_footer(content, prefix)

    content = remove_inline_markers(content)

    content = remove_ui_noise(content)

    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()

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

    test_file = None
    if len(sys.argv) > 1:
        test_file = sys.argv[1]

    total_before, total_after, processed, skipped, prefix_counts = _process_files(files, test_file)

    reduction = (1 - total_after / total_before) * 100 if total_before else 0

    _print_report(processed, skipped, prefix_counts, total_before, total_after, reduction)


if __name__ == "__main__":
    main()
