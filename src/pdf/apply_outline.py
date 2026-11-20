# INFRASTRUCTURE
import re
from pathlib import Path

from src.pdf.batch_files import (
    HEADINGS_FILE, HEADINGS_FIXED_FILE, KIND_HEADING, PLACEHOLDER, WORKER_OUTLINE, outlined_md, page_md, read_json,
)
from src.pdf.manifest import load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.worker_outputs import STATE_COMPLETE, worker_state

HEADING_MARKS = re.compile(r"^#+\s*")
LEVELS = range(0, 5)
MISSED_LEVELS = range(1, 5)


# ORCHESTRATOR
def apply_outline_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    require_outline_complete(batch_path, manifest)
    outline = read_json(batch_path, HEADINGS_FIXED_FILE)
    lines = heading_lines(read_json(batch_path, HEADINGS_FILE), outline["headings"])
    pages = outlined_pages(batch_path, manifest["pages"], lines, outline["missed"])
    write_outlined(batch_path, pages)
    return Report(format_summary(pages, lines, outline["missed"]), True)


# FUNCTIONS
def require_outline_complete(batch_dir: Path, manifest: dict) -> None:
    worker = next(worker for worker in manifest["workers"] if worker["name"] == WORKER_OUTLINE)
    state, missing = worker_state(batch_dir, worker)
    if state != STATE_COMPLETE:
        raise WorkflowError("outline_incomplete", f"the outline worker is incomplete, missing: {' '.join(missing)}")


def heading_lines(headings: list[dict], levels: list[dict]) -> dict[str, str]:
    level_of = {entry["id"]: entry["level"] for entry in levels}
    lines = {}
    for heading in headings:
        level = level_of[heading["id"]]
        if level not in LEVELS:
            raise WorkflowError("outline_level", f"heading {heading['id']} has level {level!r}, allowed are 0 to 4")
        wording = HEADING_MARKS.sub("", heading["text"]).strip()
        lines[heading["id"]] = f"{'#' * level} {wording}" if level else wording
    return lines


def outlined_pages(batch_dir: Path, pages: int, lines: dict[str, str], missed: list[dict]) -> dict[int, str]:
    result = {}
    for number in range(1, pages + 1):
        text = PLACEHOLDER.sub(lambda match: replace_heading(match, lines), (batch_dir / page_md(number)).read_text(encoding="utf-8"))
        for entry in [entry for entry in missed if entry["page"] == number]:
            text = mark_missed(text, entry)
        result[number] = text
    unknown = [entry for entry in missed if entry["page"] not in result]
    if unknown:
        raise WorkflowError("missed_heading_not_found", f"missed heading on page {unknown[0]['page']}, which does not exist")
    return result


def replace_heading(match: re.Match, lines: dict[str, str]) -> str:
    return lines[match[2]] if match[1] == KIND_HEADING else match[0]


def mark_missed(text: str, entry: dict) -> str:
    if entry["level"] not in MISSED_LEVELS:
        raise WorkflowError("outline_level", f"missed heading on page {entry['page']} has level {entry['level']!r}, allowed are 1 to 4")
    rows = text.split("\n")
    hits = [index for index, row in enumerate(rows) if row.rstrip() == entry["line"].rstrip()]
    if len(hits) != 1:
        raise WorkflowError(
            "missed_heading_not_found",
            f"page {entry['page']}: the line {entry['line']!r} occurs {len(hits)} times in {page_md(entry['page'])}, it must occur once",
        )
    rows[hits[0]] = f"{'#' * entry['level']} {rows[hits[0]].strip()}"
    return "\n".join(rows)


def write_outlined(batch_dir: Path, pages: dict[int, str]) -> None:
    for number, text in pages.items():
        (batch_dir / outlined_md(number)).write_text(text, encoding="utf-8")


def format_summary(pages: dict[int, str], lines: dict[str, str], missed: list[dict]) -> str:
    outline = [row for number in sorted(pages) for row in pages[number].split("\n") if row.startswith("#")]
    dropped = sum(1 for line in lines.values() if not line.startswith("#"))
    return "\n".join([
        f"apply-outline ok: {len(lines)} headings, {dropped} set to level 0, {len(missed)} missed headings added",
        "outline:",
        *[f"  {row}" for row in outline],
    ])
