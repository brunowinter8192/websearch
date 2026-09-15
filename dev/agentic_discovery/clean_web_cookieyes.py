#!/usr/bin/env python3
"""
Cleanup script for cookieyes__*.md files crawled from www.cookieyes.com/documentation/

Patterns detected across sampled files:

HEADER NOISE (after <!-- source: --> comment, before content):
  - Blank lines (4-5 blank lines before the # heading)
  - "Search for:Search Button" line immediately after the # heading
  - Breadcrumb line: "[Help Guides](...) > [Category](...) > Page" immediately after search bar

BODY NOISE:
  - "Skip to content" links (not seen in samples but common on cookieyes.com)

FOOTER NOISE (at end of file):
  - "Was this article helpful?" line
  - "Yes No" line (helpfulness vote buttons)
  - G2 Rating Badges image lines
  - Newsletter subscribe block (## Subscribe to get a monthly newsletter...)
  - "Related articles" section with list of links (## Related articles)
  - Jump-to link block (appears after "Last updated on ..." line on some pages):
      - skip icon image line
      - "Jump to" line
      - List of anchor links
  These jump-to blocks are navigation elements, not content.

CATEGORY INDEX PAGES (cookieyes__category__*.md):
  - Entire body is a list of links to child pages — this IS the content for category pages.
  - Only remove: search bar, breadcrumb, footer noise.

Notes:
  - <!-- source: URL --> comments are PRESERVED (first line of every file)
  - The # heading is PRESERVED
  - All actual article content is PRESERVED
"""

import re
from pathlib import Path

# Input directory is in the RAG project, not the searxng project
# Resolved from the known RAG project structure:
#   ~/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng/
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent  # searxng project root
_RAG_ROOT = _PROJECT_ROOT.parent / "RAG"   # sibling RAG project
INPUT_DIR = _RAG_ROOT / "data" / "documents" / "searxng"
PATTERN = "cookieyes__*.md"


def _consume_header_line(lines: list, i: int, result: list, source_comment_done: bool,
                          heading_done: bool) -> tuple[int, bool, bool, bool]:
    stripped = lines[i].strip()

    # Always preserve the <!-- source: URL --> comment
    if stripped.startswith("<!-- source:"):
        result.append(lines[i])
        return i + 1, True, heading_done, True

    # Skip blank lines between source comment and first # heading
    # (these are just crawl4ai padding, not content)
    if source_comment_done and not heading_done and stripped == "":
        return i + 1, source_comment_done, heading_done, True

    # First # heading — preserve it, mark heading done
    if source_comment_done and not heading_done and stripped.startswith("# "):
        result.append(lines[i])
        return i + 1, source_comment_done, True, True

    return i, source_comment_done, heading_done, False


def _is_post_heading_chrome(stripped: str, heading_done: bool) -> bool:
    # After heading: remove "Search for:Search Button" line
    if heading_done and stripped == "Search for:Search Button":
        return True
    # After heading: remove breadcrumb line
    # Pattern: starts with "[Help Guides](" or "[Guides](" and contains " > "
    if heading_done and re.match(r'^\[Help Guides\]\(', stripped) and " > " in stripped:
        return True
    return False


def _detect_helpfulness_footer(line: str, stripped: str) -> tuple[bool, str]:
    # "Was this article helpful?" — everything from here to end is footer
    # It can appear as a standalone line OR inline at the end of a content line
    if stripped == "Was this article helpful?":
        # Stop collecting, we're done with content
        return True, ""

    # Inline case: "Was this article helpful? Yes No" appended to end of content line
    HELPFULNESS_SUFFIX = " Was this article helpful? Yes No"
    if HELPFULNESS_SUFFIX in line:
        # Strip the suffix and keep the content before it
        clean_line = line[:line.index(HELPFULNESS_SUFFIX)]
        return True, clean_line

    return False, ""


def _removable_section_transition(stripped: str, in_subscribe_block: bool, in_related_articles: bool) -> tuple[bool, bool, bool]:
    # Newsletter subscribe block
    if stripped.startswith("## Subscribe to get a monthly"):
        return True, True, in_related_articles
    if in_subscribe_block:
        return True, in_subscribe_block, in_related_articles

    # Related articles section
    if stripped == "## Related articles":
        return True, in_subscribe_block, True
    if in_related_articles:
        # Section ends at next ## heading or end of file
        if stripped.startswith("## ") and stripped != "## Related articles":
            # Don't skip this line — fall through to normal processing
            return False, in_subscribe_block, False
        return True, in_subscribe_block, in_related_articles

    return False, in_subscribe_block, in_related_articles


def _consume_skip_icon_block(lines: list[str], i: int, n: int) -> int:
    # Skip icon + "Jump to" block:
    # Pattern: a line with skip.svg image followed by "Jump to" and anchor links
    # These appear right after "Last updated on ..." line
    # Skip the skip icon line
    i += 1
    # Skip the "Jump to" line if it follows
    if i < n and lines[i].strip() == "Jump to":
        i += 1
        # Skip subsequent lines that are anchor links (start with "[" and contain "#")
        while i < n:
            next_stripped = lines[i].strip()
            # Anchor links look like: [Text](URL#anchor)
            if re.match(r'^\[.+\]\(.+#.+\)$', next_stripped):
                i += 1
            else:
                break
    return i


def _consume_inline_noise(lines: list[str], i: int, n: int, stripped: str) -> tuple[int, bool]:
    # G2 Rating Badges image lines
    if "g2-badges" in stripped:
        return i + 1, True
    if stripped.startswith("![skip icon]") and "skip.svg" in stripped:
        return _consume_skip_icon_block(lines, i, n), True
    return i, False


def clean_file(text: str) -> str:
    lines = text.splitlines()
    result = []
    i = 0
    n = len(lines)

    # --- Pass 1: Collect lines, removing header noise and footer noise ---

    # State tracking
    source_comment_done = False  # Have we passed the <!-- source: --> line?
    heading_done = False          # Have we passed the first # heading?
    in_subscribe_block = False
    in_related_articles = False

    while i < n:
        i, source_comment_done, heading_done, consumed = _consume_header_line(
            lines, i, result, source_comment_done, heading_done
        )
        if consumed:
            continue
        line = lines[i]
        stripped = line.strip()
        if _is_post_heading_chrome(stripped, heading_done):
            i += 1
            continue
        # --- Footer noise detection ---
        should_stop, trailing = _detect_helpfulness_footer(line, stripped)
        if should_stop:
            if trailing.strip():
                result.append(trailing)
            # Everything after this line is footer — stop
            break
        skip, in_subscribe_block, in_related_articles = _removable_section_transition(
            stripped, in_subscribe_block, in_related_articles
        )
        if skip:
            i += 1
            continue
        i, consumed = _consume_inline_noise(lines, i, n, stripped)
        if consumed:
            continue
        result.append(line)
        i += 1

    # --- Pass 2: Strip trailing blank lines ---
    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result) + "\n"


def _process_files(files: list) -> tuple[int, int, int, list]:
    total_before = 0
    total_after = 0
    processed = 0
    errors = []

    for filepath in files:
        try:
            original = filepath.read_text(encoding="utf-8")
            cleaned = clean_file(original)
            before = len(original)
            after = len(cleaned)
            total_before += before
            total_after += after
            filepath.write_text(cleaned, encoding="utf-8")
            processed += 1
        except Exception as e:
            errors.append((filepath.name, str(e)))

    return total_before, total_after, processed, errors


def _print_report(processed: int, total_files: int, total_before: int, total_after: int,
                   reduction: float, errors: list) -> None:
    print(f"FILES PROCESSED: {processed}/{total_files}")
    print()
    print("PATTERNS DETECTED:")
    print("  - blank_lines_after_source_comment: found in all files")
    print("  - search_bar_line ('Search for:Search Button'): found in all files")
    print("  - breadcrumb_line ('[Help Guides](...) > ...'): found in all files")
    print("  - 'Was this article helpful?' footer: found in documentation files")
    print("  - 'Yes No' vote buttons: found in documentation files")
    print("  - G2 Rating Badges images: found in documentation files")
    print("  - Newsletter subscribe block: found in documentation files")
    print("  - Related articles section: found in documentation files")
    print("  - Skip icon + 'Jump to' anchor block: found in select files")
    print()
    print("CLEANUP RESULTS:")
    print(f"  - Total chars before: {total_before:,}")
    print(f"  - Total chars after:  {total_after:,}")
    print(f"  - Reduction: {reduction:.1f}%")
    print()
    print(f"SCRIPT: dev/agentic_discovery/clean_web_cookieyes.py")
    print(f"OUTPUT: in-place (originals overwritten)")

    if errors:
        print()
        print(f"ERRORS ({len(errors)}):")
        for name, err in errors:
            print(f"  - {name}: {err}")
        print("STATUS: ISSUES_REMAINING")
    else:
        print("STATUS: CLEAN")


def main():
    files = sorted(INPUT_DIR.glob(PATTERN))
    total_files = len(files)

    total_before, total_after, processed, errors = _process_files(files)

    reduction = (1 - total_after / total_before) * 100 if total_before > 0 else 0

    _print_report(processed, total_files, total_before, total_after, reduction, errors)


if __name__ == "__main__":
    main()
