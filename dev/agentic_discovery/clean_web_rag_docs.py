# INFRASTRUCTURE
from pathlib import Path
import re

INPUT_DIR = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng")

_CRAWL4AI_NAV_MARKER_RE = re.compile(r'^\[Crawl4AI Documentation')

_PLAYWRIGHT_ANCHOR_RE = re.compile(r'\[​\]\([^)]*"Direct link to[^"]*"\)')

_COPY_LINE_RE = re.compile(r'^Copy\s*$')

_TRAFILATURA_ANCHOR_RE = re.compile(r'\[#\]\([^)]*"Link to this heading"\)')


# ORCHESTRATOR

def main():
    patterns = ["playwright__*.md", "crawl4ai__*.md", "trafilatura__*.md"]
    all_files = []
    _collect_pattern_files(patterns, all_files)

    if not all_files:
        _print_no_matching_files()
        return

    domain_stats: dict[str, list] = {
        "playwright": [0, 0, 0, 0],
        "crawl4ai":   [0, 0, 0, 0],
        "trafilatura":[0, 0, 0, 0],
    }

    _accumulate_domain_stats(all_files, domain_stats)

    total_before = _compute_total_before(domain_stats)
    total_after = _compute_total_after(domain_stats)
    reduction = _compute_reduction(total_after, total_before)

    _print_line(all_files)
    print()
    _print_domain_stats(domain_stats)
    print()
    _print_total_chars_before(total_before, total_after, reduction)


# FUNCTIONS

def _collect_pattern_files(patterns, all_files):
    for pattern in patterns:
        all_files.extend(sorted(INPUT_DIR.glob(pattern)))


def _print_no_matching_files():
    print(f"No matching files found in {INPUT_DIR}")


def _accumulate_domain_stats(all_files, domain_stats):
    for path in all_files:
        name = path.name
        if name.startswith("playwright__"):
            key = "playwright"
        elif name.startswith("crawl4ai__"):
            key = "crawl4ai"
        else:
            key = "trafilatura"

        before, after = clean_file(path)
        s = domain_stats[key]
        s[0] += 1
        s[1] += before
        s[2] += after
        if before != after:
            s[3] += 1


def _compute_total_before(domain_stats):
    total_before = sum(s[1] for s in domain_stats.values())
    return total_before


def _compute_total_after(domain_stats):
    total_after = sum(s[2] for s in domain_stats.values())
    return total_after


def _compute_reduction(total_after, total_before):
    reduction = (1 - total_after / total_before) * 100 if total_before else 0
    return reduction


def _print_line(all_files):
    print("=" * 60)
    print(f"FILES PROCESSED: {len(all_files)} total")


def _print_domain_stats(domain_stats):
    for domain, (n, before, after, changed) in domain_stats.items():
        dom_reduction = (1 - after / before) * 100 if before else 0
        print(f"  {domain}: {n} files, {changed} modified, "
              f"{before:,} → {after:,} chars ({dom_reduction:.1f}% reduction)")


def _print_total_chars_before(total_before, total_after, reduction):
    print(f"TOTAL chars before: {total_before:,}")
    print(f"TOTAL chars after:  {total_after:,}")
    print(f"TOTAL reduction:    {reduction:.1f}%")
    print("=" * 60)


def clean_file(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    chars_before = len(text)

    lines = text.splitlines(keepends=True)
    source_comment = extract_source_comment(lines)

    name = path.name
    if name.startswith("playwright__"):
        domain_cleaner = clean_playwright
        content_start = find_content_start(lines)
    elif name.startswith("crawl4ai__"):
        domain_cleaner = clean_crawl4ai
        content_start = find_crawl4ai_content_start(lines)
    elif name.startswith("trafilatura__"):
        domain_cleaner = clean_trafilatura
        content_start = find_content_start(lines)
    else:
        return chars_before, chars_before

    if content_start == -1:
        content_lines = lines
    else:
        content_lines = lines[content_start:]

    content_lines = domain_cleaner(content_lines)

    cleaned = assemble(source_comment, content_lines)
    path.write_text(cleaned, encoding="utf-8")

    return chars_before, len(cleaned)


def extract_source_comment(lines: list[str]) -> str:
    for line in lines[:4]:
        if line.startswith("<!-- source:"):
            return line.rstrip()
    return ""


def clean_playwright(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if re.match(r'^\[(?:Previous|Next)\b', line):
            break
        line = _PLAYWRIGHT_ANCHOR_RE.sub("", line)
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


def clean_crawl4ai(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if _is_crawl4ai_footer_start(line):
            break
        if _COPY_LINE_RE.match(line):
            continue
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


def find_crawl4ai_content_start(lines: list[str]) -> int:
    nav_seen = False
    nav_start_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _CRAWL4AI_NAV_MARKER_RE.match(stripped):
            nav_seen = True
            nav_start_idx = i
        if nav_seen and (line.startswith("# ") or line.startswith("## ")):
            return i

    if nav_seen and nav_start_idx >= 0:
        for i in range(nav_start_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            if stripped.startswith("*") or stripped.startswith("-") or stripped.startswith("["):
                continue
            if stripped == "×":
                continue
            return i

    return find_content_start(lines)


def clean_trafilatura(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if _is_trafilatura_footer_start(line):
            break
        line = _TRAFILATURA_ANCHOR_RE.sub("", line)
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


def assemble(source_comment: str, content_lines: list[str]) -> str:
    parts = []
    if source_comment:
        parts.append(source_comment + "\n\n")
    parts.append("".join(content_lines))
    result = "".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


def find_content_start(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith("# ") or line.startswith("## "):
            return i
    return -1


def strip_trailing_blanks(lines: list[str]) -> list[str]:
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def _is_crawl4ai_footer_start(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("#### On this page"):
        return True
    if stripped.startswith("> Feedback"):
        return True
    if stripped in ("xClose", "Type to start searching"):
        return True
    if stripped.startswith("[ Ask AI ]"):
        return True
    return False


def _is_trafilatura_footer_start(line: str) -> bool:
    stripped = line.strip()
    if re.match(r'^\[ previous ', stripped) or re.match(r'^\[previous ', stripped):
        return True
    if stripped == "On this page":
        return True
    if stripped == "### This Page":
        return True
    return False


if __name__ == "__main__":
    main()
