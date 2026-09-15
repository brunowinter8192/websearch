#!/usr/bin/env python3
"""
Cleanup script for platform.claude.com/docs pages crawled via Crawl4AI.
Input: anthropic__*.md files in the target directory
Patterns fixed:
  1. Reduce excessive blank lines after source comment (4-6 blanks → 1 blank)
  2. Merge broken headings: "## \n<text>" → "## <text>" (applies to ##, ###, ####, #)
  3. Remove end-of-file card navigation links (concatenated [ text ](url) blocks on last line)
"""

import re
from pathlib import Path

INPUT_DIR = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng")
PATTERN = "anthropic__*.md"

# Matches multiple consecutive inline card links: [ text ](url)[ text ](url)...
CARD_LINK_RE = re.compile(r'^\[.+?\]\(https?://[^)]+\)(\[.+?\]\(https?://[^)]+\))+\s*$')


def _compress_header_and_merge_headings(lines: list[str]) -> list[str]:
    result = []
    i = 0

    # --- Pass 1: Compress blank lines after source comment and merge broken headings ---
    in_source_header = True  # Track whether we're still in the post-source-comment blank block

    while i < len(lines):
        line = lines[i]

        # Compress blank lines right after the <!-- source: --> comment
        if in_source_header and line.strip() == "":
            # Consume all consecutive blank lines, emit exactly one
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            result.append("")
            in_source_header = False
            continue

        # Once we hit non-blank content, we're past the header
        if in_source_header and line.strip() != "":
            if not line.startswith("<!-- source:"):
                in_source_header = False

        # Merge broken headings: lone heading marker followed by text on next line
        # Pattern: line is exactly "## " or "### " or "#### " or "# " (with trailing space)
        if line in ("# ", "## ", "### ", "#### ") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith("#"):
                # Merge into single heading line
                result.append(line.rstrip() + " " + next_line.strip())
                i += 2
                continue

        result.append(line)
        i += 1

    return result


def _strip_trailing_card_nav(result: list[str]) -> list[str]:
    # --- Pass 2: Remove end-of-file card navigation ---
    # Walk backwards from the end, removing lines that are pure card-link concatenations
    # Stop as soon as we hit a line that isn't a card block or blank
    j = len(result) - 1
    while j >= 0:
        stripped = result[j].strip()
        if stripped == "":
            j -= 1
            continue
        if CARD_LINK_RE.match(result[j]):
            j -= 1
            continue
        break

    # Keep lines 0..j (inclusive), strip trailing blanks
    result = result[: j + 1]
    while result and result[-1].strip() == "":
        result.pop()

    return result


def clean_file(content: str) -> str:
    lines = content.split("\n")
    result = _compress_header_and_merge_headings(lines)
    result = _strip_trailing_card_nav(result)
    return "\n".join(result) + "\n"


def main():
    files = sorted(INPUT_DIR.glob(PATTERN))
    if not files:
        print(f"No files matched {PATTERN} in {INPUT_DIR}")
        return

    total_before = 0
    total_after = 0
    processed = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        cleaned = clean_file(original)

        total_before += len(original)
        total_after += len(cleaned)
        processed += 1

        if cleaned != original:
            path.write_text(cleaned, encoding="utf-8")

    reduction = (total_before - total_after) / total_before * 100 if total_before else 0
    print(f"FILES PROCESSED: {processed}")
    print(f"Total chars before: {total_before:,}")
    print(f"Total chars after:  {total_after:,}")
    print(f"Reduction: {reduction:.1f}%")


if __name__ == "__main__":
    main()
