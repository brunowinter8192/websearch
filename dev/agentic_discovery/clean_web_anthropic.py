#!/usr/bin/env python3
# INFRASTRUCTURE
import re
from pathlib import Path

INPUT_DIR = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng")
PATTERN = "anthropic__*.md"

CARD_LINK_RE = re.compile(r'^\[.+?\]\(https?://[^)]+\)(\[.+?\]\(https?://[^)]+\))+\s*$')


# ORCHESTRATOR

def main():
    files = sorted(INPUT_DIR.glob(PATTERN))
    if not files:
        _print_no_files_matched()
        return

    total_before = 0
    total_after = 0
    processed = 0

    total_before, total_after, processed = _clean_files(files, total_before, total_after, processed)

    reduction = _compute_reduction(total_before, total_after)
    _print_files_processed(processed, total_before, total_after, reduction)


# FUNCTIONS

def _print_no_files_matched():
    print(f"No files matched {PATTERN} in {INPUT_DIR}")


def _clean_files(files, total_before, total_after, processed):
    for path in files:
        original = path.read_text(encoding="utf-8")
        cleaned = clean_file(original)

        total_before += len(original)
        total_after += len(cleaned)
        processed += 1

        if cleaned != original:
            path.write_text(cleaned, encoding="utf-8")
    return total_before, total_after, processed


def _compute_reduction(total_before, total_after):
    reduction = (total_before - total_after) / total_before * 100 if total_before else 0
    return reduction


def _print_files_processed(processed, total_before, total_after, reduction):
    print(f"FILES PROCESSED: {processed}")
    print(f"Total chars before: {total_before:,}")
    print(f"Total chars after:  {total_after:,}")
    print(f"Reduction: {reduction:.1f}%")


def clean_file(content: str) -> str:
    lines = content.split("\n")
    result = _compress_header_and_merge_headings(lines)
    result = _strip_trailing_card_nav(result)
    return "\n".join(result) + "\n"


def _compress_header_and_merge_headings(lines: list[str]) -> list[str]:
    result = []
    i = 0

    in_source_header = True

    while i < len(lines):
        line = lines[i]

        if in_source_header and line.strip() == "":
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            result.append("")
            in_source_header = False
            continue

        if in_source_header and line.strip() != "":
            if not line.startswith("<!-- source:"):
                in_source_header = False

        if line in ("# ", "## ", "### ", "#### ") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith("#"):
                result.append(line.rstrip() + " " + next_line.strip())
                i += 2
                continue

        result.append(line)
        i += 1

    return result


def _strip_trailing_card_nav(result: list[str]) -> list[str]:
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

    result = result[: j + 1]
    while result and result[-1].strip() == "":
        result.pop()

    return result


if __name__ == "__main__":
    main()
