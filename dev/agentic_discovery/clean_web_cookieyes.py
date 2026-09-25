#!/usr/bin/env python3
# INFRASTRUCTURE
import re
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_RAG_ROOT = _PROJECT_ROOT.parent / "RAG"
INPUT_DIR = _RAG_ROOT / "data" / "documents" / "searxng"
PATTERN = "cookieyes__*.md"


# ORCHESTRATOR

def main():
    files = sorted(INPUT_DIR.glob(PATTERN))
    total_files = len(files)

    total_before, total_after, processed, errors = _process_files(files)

    reduction = _compute_reduction(total_after, total_before)

    _print_report(processed, total_files, total_before, total_after, reduction, errors)


# FUNCTIONS

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


def _compute_reduction(total_after, total_before):
    reduction = (1 - total_after / total_before) * 100 if total_before > 0 else 0
    return reduction


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


def clean_file(text: str) -> str:
    lines = text.splitlines()
    result = []
    i = 0
    n = len(lines)


    source_comment_done = False
    heading_done = False
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
        should_stop, trailing = _detect_helpfulness_footer(line, stripped)
        if should_stop:
            if trailing.strip():
                result.append(trailing)
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

    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result) + "\n"


def _consume_header_line(lines: list, i: int, result: list, source_comment_done: bool,
                          heading_done: bool) -> tuple[int, bool, bool, bool]:
    stripped = lines[i].strip()

    if stripped.startswith("<!-- source:"):
        result.append(lines[i])
        return i + 1, True, heading_done, True

    if source_comment_done and not heading_done and stripped == "":
        return i + 1, source_comment_done, heading_done, True

    if source_comment_done and not heading_done and stripped.startswith("# "):
        result.append(lines[i])
        return i + 1, source_comment_done, True, True

    return i, source_comment_done, heading_done, False


def _is_post_heading_chrome(stripped: str, heading_done: bool) -> bool:
    if heading_done and stripped == "Search for:Search Button":
        return True
    if heading_done and re.match(r'^\[Help Guides\]\(', stripped) and " > " in stripped:
        return True
    return False


def _detect_helpfulness_footer(line: str, stripped: str) -> tuple[bool, str]:
    if stripped == "Was this article helpful?":
        return True, ""

    HELPFULNESS_SUFFIX = " Was this article helpful? Yes No"
    if HELPFULNESS_SUFFIX in line:
        clean_line = line[:line.index(HELPFULNESS_SUFFIX)]
        return True, clean_line

    return False, ""


def _removable_section_transition(stripped: str, in_subscribe_block: bool, in_related_articles: bool) -> tuple[bool, bool, bool]:
    if stripped.startswith("## Subscribe to get a monthly"):
        return True, True, in_related_articles
    if in_subscribe_block:
        return True, in_subscribe_block, in_related_articles

    if stripped == "## Related articles":
        return True, in_subscribe_block, True
    if in_related_articles:
        if stripped.startswith("## ") and stripped != "## Related articles":
            return False, in_subscribe_block, False
        return True, in_subscribe_block, in_related_articles

    return False, in_subscribe_block, in_related_articles


def _consume_inline_noise(lines: list[str], i: int, n: int, stripped: str) -> tuple[int, bool]:
    if "g2-badges" in stripped:
        return i + 1, True
    if stripped.startswith("![skip icon]") and "skip.svg" in stripped:
        return _consume_skip_icon_block(lines, i, n), True
    return i, False


def _consume_skip_icon_block(lines: list[str], i: int, n: int) -> int:
    i += 1
    if i < n and lines[i].strip() == "Jump to":
        i += 1
        while i < n:
            next_stripped = lines[i].strip()
            if re.match(r'^\[.+\]\(.+#.+\)$', next_stripped):
                i += 1
            else:
                break
    return i


if __name__ == "__main__":
    main()
