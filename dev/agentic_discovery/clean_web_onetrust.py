#!/usr/bin/env python3
# INFRASTRUCTURE
import re
import sys
from pathlib import Path

INPUT_DIR = Path(__file__).parent.parent.parent.parent / "RAG" / "data" / "documents" / "searxng"
FILE_PATTERN = "onetrust__*.md"

RE_EMPTY_ANCHOR = re.compile(r'^\[\]\(https://[^\)]+\)\s*$')

RE_SPLIT_HEADING = re.compile(r'^(#{1,6})\s*$')

RE_PAGINATION = re.compile(r'^\d+ of \d+\[\]\([^\)]*\)\s*$')

RE_NAV_LINK_LINE = re.compile(r'^(\[([^\]]+)\]\([^\)]+\))+\s*$')


# FUNCTIONS

def main(test_file: str = None):
    if test_file:
        p = Path(test_file)
        before, after = process_file(p)
        print(f"TEST: {p.name}")
        print(f"  Before: {before} chars")
        print(f"  After:  {after} chars")
        print(f"  Reduction: {(before - after) / before * 100:.1f}%")
        return

    files = sorted(INPUT_DIR.glob(FILE_PATTERN))
    if not files:
        print(f"No files found matching {INPUT_DIR}/{FILE_PATTERN}")
        sys.exit(1)

    total_before = 0
    total_after = 0
    processed = 0

    for path in files:
        before, after = process_file(path)
        total_before += before
        total_after += after
        processed += 1
        if processed % 100 == 0:
            print(f"  Processed {processed}/{len(files)} files...")

    reduction = (total_before - total_after) / total_before * 100 if total_before > 0 else 0
    print(f"\nFILES PROCESSED: {processed}")
    print(f"Total chars before: {total_before:,}")
    print(f"Total chars after:  {total_after:,}")
    print(f"Reduction: {reduction:.1f}%")


def process_file(path: Path) -> tuple[int, int]:
    original = path.read_text(encoding='utf-8')
    cleaned = clean_content(original)
    path.write_text(cleaned, encoding='utf-8')
    return len(original), len(cleaned)


def clean_content(text: str) -> str:
    lines = text.split('\n')
    result = []

    source_line, content_start = _extract_source_and_content_start(lines)
    if source_line is not None:
        result.append(source_line)
        result.append('')

    content_lines = lines[content_start:]
    content_lines = _strip_footer_nav(content_lines)
    result.extend(_filter_content_lines(content_lines))

    final = _collapse_and_trim(result)
    return '\n'.join(final) + '\n'


def _extract_source_and_content_start(lines: list[str]) -> tuple[str | None, int]:
    if lines and lines[0].startswith('<!-- source:'):
        source_line = lines[0]
        i = 1
        while i < len(lines) and not lines[i].startswith('#'):
            i += 1
        return source_line, i
    return None, 0


def _strip_footer_nav(content_lines: list[str]) -> list[str]:
    end = len(content_lines)
    while end > 0 and content_lines[end - 1].strip() == '':
        end -= 1

    if end >= 2 and is_footer_nav_line(content_lines[end - 1]):
        end -= 1
        while end > 0 and content_lines[end - 1].strip() in ('* * *', '---', '***'):
            end -= 1
        while end > 0 and content_lines[end - 1].strip() == '':
            end -= 1

    saved_end = end
    temp_end = end
    while temp_end > 0 and content_lines[temp_end - 1].strip() in ('* * *', '---', '***'):
        temp_end -= 1
    while temp_end > 0 and content_lines[temp_end - 1].strip() == '':
        temp_end -= 1
    if temp_end < saved_end and temp_end > 0:
        end = temp_end

    return content_lines[:end]


def _filter_content_lines(content_lines: list[str]) -> list[str]:
    result = []
    i = 0
    while i < len(content_lines):
        line = content_lines[i]

        if RE_EMPTY_ANCHOR.match(line):
            i += 1
            continue

        if RE_PAGINATION.match(line):
            i += 1
            continue

        merge = _try_merge_split_heading(content_lines, i)
        if merge is not None:
            merged_heading, next_i = merge
            if merged_heading:
                result.append(merged_heading)
            i = next_i
            continue

        result.append(line)
        i += 1

    return result


def _collapse_and_trim(lines: list[str]) -> list[str]:
    final = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            continue
        final.append(line)
        prev_blank = is_blank

    while final and final[-1].strip() == '':
        final.pop()

    return final


def is_footer_nav_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(RE_NAV_LINK_LINE.match(stripped))


def _try_merge_split_heading(content_lines: list[str], i: int) -> tuple[str, int] | None:
    line = content_lines[i]
    split_match = RE_SPLIT_HEADING.match(line)
    if not split_match:
        return None

    hashes = split_match.group(1)
    next_i = i + 1
    while next_i < len(content_lines) and content_lines[next_i].strip() == '':
        next_i += 1
    if next_i < len(content_lines):
        next_line = content_lines[next_i].strip()
        if next_line and not next_line.startswith('#') and not RE_EMPTY_ANCHOR.match(next_line):
            return f"{hashes} {next_line}", next_i + 1

    return "", i + 1


if __name__ == '__main__':
    test_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(test_arg)
