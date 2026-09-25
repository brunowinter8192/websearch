# INFRASTRUCTURE
import re
from pathlib import Path

INPUT_DIR = Path(__file__).parent.parent.parent.parent / "RAG" / "data" / "documents" / "searxng"
FILE_PATTERN = "tor__*.md"

FOOTER_START_PATTERN = re.compile(
    r"^\s*\*\s*\[[^\]]+\]\(https://www\.torproject\.org/(?:[a-z]{2}(?:-[A-Z]{2})?/)?about/jobs/\)"
)

UI_WIDGET_LINES = {
    "View for: ",
    "View for:",
    "Expand all Collapse all",
}


# ORCHESTRATOR

def main() -> None:
    files = sorted(INPUT_DIR.glob(FILE_PATTERN))
    if not files:
        print(f"No files found matching {INPUT_DIR / FILE_PATTERN}")
        return

    total_before, total_after, pattern_counts = _process_files(files)

    reduction = (1 - total_after / total_before) * 100 if total_before > 0 else 0

    _print_report(len(files), pattern_counts, total_before, total_after, reduction)


# FUNCTIONS

def _process_files(files: list) -> tuple[int, int, dict]:
    total_before = 0
    total_after = 0
    pattern_counts = {
        "footer_removed": 0,
        "view_for_removed": 0,
        "expand_collapse_removed": 0,
    }

    for path in files:
        text_before = path.read_text(encoding="utf-8")
        lines_before = text_before.splitlines()

        has_footer, has_view_for, has_expand = _detect_patterns(lines_before)

        before, after = clean_file(path)
        total_before += before
        total_after += after

        if has_footer:
            pattern_counts["footer_removed"] += 1
        if has_view_for:
            pattern_counts["view_for_removed"] += 1
        if has_expand:
            pattern_counts["expand_collapse_removed"] += 1

    return total_before, total_after, pattern_counts


def _print_report(num_files: int, pattern_counts: dict, total_before: int, total_after: int,
                   reduction: float) -> None:
    print(f"FILES PROCESSED: {num_files}")
    print()
    print("PATTERNS DETECTED:")
    print(f"  - footer_block (Jobs/social/Copyleft): found in {pattern_counts['footer_removed']}/{num_files} files")
    print(f"  - view_for_widget: found in {pattern_counts['view_for_removed']}/{num_files} files")
    print(f"  - expand_collapse_widget: found in {pattern_counts['expand_collapse_removed']}/{num_files} files")
    print()
    print("CLEANUP RESULTS:")
    print(f"  - Total chars before: {total_before:,}")
    print(f"  - Total chars after:  {total_after:,}")
    print(f"  - Reduction: {reduction:.1f}%")
    print()
    print(f"SCRIPT: dev/agentic_discovery/clean_web_tor.py")
    print(f"OUTPUT: in-place (originals overwritten)")
    print(f"STATUS: CLEAN")


def _detect_patterns(lines_before: list) -> tuple[bool, bool, bool]:
    has_footer = any(FOOTER_START_PATTERN.match(l) for l in lines_before)
    has_view_for = any(l.strip() in {"View for: ", "View for:"} for l in lines_before)
    has_expand = any("Expand all Collapse all" in l for l in lines_before)
    return has_footer, has_view_for, has_expand


def clean_file(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    chars_before = len(text)

    lines = text.splitlines(keepends=True)
    output_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")

        if FOOTER_START_PATTERN.match(stripped):
            while output_lines and output_lines[-1].strip() == "":
                output_lines.pop()
            break

        if stripped in UI_WIDGET_LINES:
            i += 1
            if stripped in {"View for: ", "View for:"} and i < len(lines):
                i += 1
            continue

        output_lines.append(line)
        i += 1

    result = "".join(output_lines)
    result = result.rstrip("\n") + "\n"

    path.write_text(result, encoding="utf-8")
    return chars_before, len(result)


if __name__ == "__main__":
    main()
