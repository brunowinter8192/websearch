#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

DESCRIPTION = """
clean.py — URL-spanning cleanup of raw scraped markdown for RAG indexing.

Reads raw .md files from a 02_raw_data/<ts>/ directory, applies cleanup patterns,
writes cleaned versions to dev/scrape_pipeline/03_cleanup/cleaned_data/<ts>/.

Patterns are URL-spanning heuristics — NOT site-specific. Each pattern is documented
inline with the URL where it was first discovered. New patterns are added as we
encounter new chrome variants while iterating through the raw output set.

Usage:
    ./venv/bin/python dev/scrape_pipeline/03_cleanup/clean.py
    ./venv/bin/python dev/scrape_pipeline/03_cleanup/clean.py --input dev/scrape_pipeline/02_raw_data/<ts>/
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR_DEFAULT = PROJECT_ROOT / "dev" / "scrape_pipeline" / "02_raw_data"
CLEANED_DIR_BASE = PROJECT_ROOT / "dev" / "scrape_pipeline" / "03_cleanup" / "cleaned_data"

MIN_CONTENT_BYTES = 500


def cleanup_workflow(input_dir: Path, output_dir: Path) -> None:
    raw_files = sorted(p for p in input_dir.glob("*.md") if p.name != "02_raw_report.md")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"clean.py — input: {input_dir}", file=sys.stderr)
    print(f"           output: {output_dir}", file=sys.stderr)
    print(f"Files: {len(raw_files)}\n", file=sys.stderr)

    rows = []
    for f in raw_files:
        raw = f.read_text(encoding="utf-8")
        raw_size = len(raw)

        if raw_size < MIN_CONTENT_BYTES:
            rows.append((f.name, raw_size, 0, "skipped: near-empty"))
            print(f"  SKIP  {f.name:80s}  raw={raw_size}B (near-empty)", file=sys.stderr)
            continue

        cleaned = clean_markdown(raw)
        out_path = output_dir / f.name
        out_path.write_text(cleaned, encoding="utf-8")

        delta = raw_size - len(cleaned)
        pct = 100 * delta / raw_size
        rows.append((f.name, raw_size, len(cleaned), f"{delta:,}B ({pct:.1f}%) stripped"))
        print(f"  OK    {f.name:80s}  raw={raw_size:>7,}  out={len(cleaned):>7,}  -{pct:5.1f}%", file=sys.stderr)

    write_summary(output_dir, rows)


def clean_markdown(text: str) -> str:
    text = strip_hn_top_nav(text)
    text = strip_github_chrome(text)
    text = strip_pre_h1_chrome(text)
    text = strip_pre_content_chrome(text)
    text = strip_skip_links(text)
    text = strip_sphinx_anchors(text)
    text = strip_tail_chrome(text)
    text = collapse_blank_lines(text)
    return text


GITHUB_SOURCE_RE = re.compile(
    r"^<!-- source: https?://github\.com/[^/]+/[^/]+/(?:issues|pull)/(\d+)",
    re.MULTILINE,
)

def strip_github_chrome(text: str) -> str:
    src = SOURCE_RE.search(text)
    gh = GITHUB_SOURCE_RE.search(text)
    if not (src and gh):
        return text
    issue_n = gh.group(1)
    title_re = re.compile(rf"^# +.+ #{issue_n}\s*$", re.MULTILINE)
    m = title_re.search(text)
    if not m or m.start() <= src.end():
        return text
    return text[:src.end()] + "\n\n" + text[m.start():]


SOURCE_RE = re.compile(r"^<!-- source: .* -->\s*$", re.MULTILINE)
H1_RE = re.compile(r"^# +\S", re.MULTILINE)
MIN_TITLE_PROSE_CHARS = 200

def gap_substantive_chars(gap: str) -> int:
    total = 0
    for line in gap.split("\n"):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|"):
            continue
        if re.match(r"^\s*[\*\-]?\s*\[[^\]]*\]\([^)]*\)\s*$", s):
            continue
        prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        prose = re.sub(r"[\*\_\`\!]", "", prose)
        if len(prose.strip()) > 60:
            total += len(prose.strip())
    return total

def find_title_h1(text: str) -> int:
    h1_positions = [m.start() for m in H1_RE.finditer(text)]
    if not h1_positions:
        return -1
    for i, pos in enumerate(h1_positions):
        next_pos = h1_positions[i + 1] if i + 1 < len(h1_positions) else len(text)
        if gap_substantive_chars(text[pos:next_pos]) >= MIN_TITLE_PROSE_CHARS:
            return pos
    return h1_positions[0]

def strip_pre_h1_chrome(text: str) -> str:
    src = SOURCE_RE.search(text)
    title_pos = find_title_h1(text)
    if not src or title_pos == -1 or title_pos <= src.end():
        return text
    return text[:src.end()] + "\n\n" + text[title_pos:]


NAV_LINE_RE = re.compile(r"^\s*[\*\-]?\s*\[[^\]]*\]\([^)]*\)\s*$")
GENERIC_NAV_PHRASES = re.compile(r"^\s*(Toggle navigation|Menu|Search this site)\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^#{1,6} +\S")

def visible_text_len(s: str) -> int:
    s = re.sub(r"\[!\[[^\]]*\]\([^)]*\)([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[\*\_\`]", "", s)
    return len(s.strip())

def is_substantive_line(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("<!--"):
        return False
    if HEADING_RE.match(s):
        return True
    if NAV_LINE_RE.match(s):
        return False
    if GENERIC_NAV_PHRASES.match(s):
        return False
    return visible_text_len(s) > 60

def strip_pre_content_chrome(text: str) -> str:
    if H1_RE.search(text):
        return text
    src = SOURCE_RE.search(text)
    if not src:
        return text
    after = text[src.end():]
    lines = after.split("\n")
    skip_count = 0
    for i, line in enumerate(lines):
        if is_substantive_line(line):
            skip_count = i
            break
    else:
        return text
    return text[:src.end()] + "\n\n" + "\n".join(lines[skip_count:])


SKIP_LINK_RE = re.compile(
    r"^\s*\[\s*Skip to [^\]]+\]\([^)]+\)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

def strip_skip_links(text: str) -> str:
    return SKIP_LINK_RE.sub("", text)


SPHINX_ANCHOR_RE = re.compile(
    r'\[(#|¶|\xb6)\]\([^)]+\s+"(?:Link to this heading|Permalink[^"]*)"\)',
)

def strip_sphinx_anchors(text: str) -> str:
    return SPHINX_ANCHOR_RE.sub("", text)


TAIL_MARKERS = [
    re.compile(r"^## Continue reading\s*$", re.MULTILINE),
    re.compile(r"^## Related posts?\s*$", re.MULTILINE),
    re.compile(r"^## Related articles?\s*$", re.MULTILINE),
    re.compile(r"^## Comments\s*$", re.MULTILINE),
    re.compile(r"^## Webmentions?\s*$", re.MULTILINE),
    re.compile(r"^## Replies\s*$", re.MULTILINE),
    re.compile(r"^You are here:\s*$", re.MULTILINE),
    re.compile(r"^\s*Copyright\s+\d{4}", re.MULTILINE),
]

def strip_tail_chrome(text: str) -> str:
    earliest = len(text)
    for pat in TAIL_MARKERS:
        m = pat.search(text)
        if m and m.start() < earliest:
            earliest = m.start()
    return text[:earliest].rstrip() + "\n"


HN_SOURCE_RE = re.compile(r"^<!-- source: https?://news\.ycombinator\.com/", re.MULTILINE)
HN_NAV_SIG = re.compile(r"\[Hacker News\]\(https://news\.ycombinator\.com/news\)")
HN_STORY_ROW = re.compile(r"\(https://news\.ycombinator\.com/vote\?id=\d+", re.MULTILINE)

def strip_hn_top_nav(text: str) -> str:
    if not HN_SOURCE_RE.search(text):
        return text
    src = SOURCE_RE.search(text)
    nav_match = HN_NAV_SIG.search(text)
    story_match = HN_STORY_ROW.search(text)
    if not (src and nav_match and story_match):
        return text
    line_start = text.rfind("\n", 0, story_match.start()) + 1
    return text[:src.end()] + "\n\n" + text[line_start:]


BLANK_LINES_RE = re.compile(r"\n{4,}")

def collapse_blank_lines(text: str) -> str:
    return BLANK_LINES_RE.sub("\n\n\n", text)


def write_summary(output_dir: Path, rows: list) -> None:
    lines = [
        "# Cleanup Run Summary",
        "",
        f"**Output:** `{output_dir}`",
        f"**Files:** {len(rows)}",
        "",
        "| File | Raw bytes | Cleaned bytes | Delta |",
        "|------|-----------|---------------|-------|",
    ]
    for name, raw, cleaned, note in rows:
        short = name[:60] + ("…" if len(name) > 60 else "")
        lines.append(f"| {short} | {raw:,} | {cleaned:,} | {note} |")

    (output_dir / "_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_latest_raw_dir() -> Path:
    candidates = sorted(p for p in RAW_DIR_DEFAULT.iterdir() if p.is_dir())
    if not candidates:
        raise SystemExit(f"No subdirs in {RAW_DIR_DEFAULT}")
    return candidates[-1]


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--input", help="Path to raw outputs dir (default: latest in 02_raw_data/)")
    parser.add_argument("--output", help="Output dir (default: 03_cleanup/cleaned_data/<ts>/)")
    args = parser.parse_args()

    input_dir = Path(args.input) if args.input else find_latest_raw_dir()
    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = CLEANED_DIR_BASE / ts

    cleanup_workflow(input_dir, output_dir)


if __name__ == "__main__":
    main()
