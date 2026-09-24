from pathlib import Path
import re

INPUT_DIR = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/data/documents/searxng")


def extract_source_comment(lines: list[str]) -> str:
    for line in lines[:4]:
        if line.startswith("<!-- source:"):
            return line.rstrip()
    return ""


def find_content_start(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith("# ") or line.startswith("## "):
            return i
    return -1


_CRAWL4AI_NAV_MARKER_RE = re.compile(r'^\[Crawl4AI Documentation')


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


def strip_trailing_blanks(lines: list[str]) -> list[str]:
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def assemble(source_comment: str, content_lines: list[str]) -> str:
    parts = []
    if source_comment:
        parts.append(source_comment + "\n\n")
    parts.append("".join(content_lines))
    result = "".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


_PLAYWRIGHT_ANCHOR_RE = re.compile(r'\[​\]\([^)]*"Direct link to[^"]*"\)')


def clean_playwright(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if re.match(r'^\[(?:Previous|Next)\b', line):
            break
        line = _PLAYWRIGHT_ANCHOR_RE.sub("", line)
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


_COPY_LINE_RE = re.compile(r'^Copy\s*$')


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


def clean_crawl4ai(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if _is_crawl4ai_footer_start(line):
            break
        if _COPY_LINE_RE.match(line):
            continue
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


_TRAFILATURA_ANCHOR_RE = re.compile(r'\[#\]\([^)]*"Link to this heading"\)')


def _is_trafilatura_footer_start(line: str) -> bool:
    stripped = line.strip()
    if re.match(r'^\[ previous ', stripped) or re.match(r'^\[previous ', stripped):
        return True
    if stripped == "On this page":
        return True
    if stripped == "### This Page":
        return True
    return False


def clean_trafilatura(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if _is_trafilatura_footer_start(line):
            break
        line = _TRAFILATURA_ANCHOR_RE.sub("", line)
        cleaned.append(line)
    return strip_trailing_blanks(cleaned)


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


def main():
    patterns = ["playwright__*.md", "crawl4ai__*.md", "trafilatura__*.md"]
    all_files = []
    for pattern in patterns:
        all_files.extend(sorted(INPUT_DIR.glob(pattern)))

    if not all_files:
        print(f"No matching files found in {INPUT_DIR}")
        return

    domain_stats: dict[str, list] = {
        "playwright": [0, 0, 0, 0],
        "crawl4ai":   [0, 0, 0, 0],
        "trafilatura":[0, 0, 0, 0],
    }

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

    total_before = sum(s[1] for s in domain_stats.values())
    total_after = sum(s[2] for s in domain_stats.values())
    reduction = (1 - total_after / total_before) * 100 if total_before else 0

    print("=" * 60)
    print(f"FILES PROCESSED: {len(all_files)} total")
    print()
    for domain, (n, before, after, changed) in domain_stats.items():
        dom_reduction = (1 - after / before) * 100 if before else 0
        print(f"  {domain}: {n} files, {changed} modified, "
              f"{before:,} → {after:,} chars ({dom_reduction:.1f}% reduction)")
    print()
    print(f"TOTAL chars before: {total_before:,}")
    print(f"TOTAL chars after:  {total_after:,}")
    print(f"TOTAL reduction:    {reduction:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
