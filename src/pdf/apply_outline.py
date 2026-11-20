# INFRASTRUCTURE
import re
from pathlib import Path

from src.pdf.batch_files import (
    HEADINGS_FILE, HEADINGS_FIXED_FILE, KIND_HEADING, PLACEHOLDER, REPAIR_PENDING, WORKER_OUTLINE, fixed_page_md, outlined_md, page_md,
    read_json,
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
    pages, moved = marked_pages(headed_pages(batch_path, manifest["pages"], lines), outline["missed"])
    require_no_repair_started(batch_path, pages)
    write_outlined(batch_path, pages)
    return Report(format_summary(pages, lines, outline["missed"], moved), True)


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


def headed_pages(batch_dir: Path, pages: int, lines: dict[str, str]) -> dict[int, str]:
    return {
        number: PLACEHOLDER.sub(lambda match: replace_heading(match, lines), (batch_dir / page_md(number)).read_text(encoding="utf-8"))
        for number in range(1, pages + 1)
    }


def replace_heading(match: re.Match, lines: dict[str, str]) -> str:
    return lines[match[2]] if match[1] == KIND_HEADING else match[0]


def marked_pages(pages: dict[int, str], missed: list[dict]) -> tuple[dict[int, str], list[str]]:
    result, moved = dict(pages), []
    for entry in missed:
        require_missed_entry(result, entry)
        number, index = missed_row(result, entry)
        if number != entry["page"]:
            moved.append(f"{entry['line'].strip()!r} named page {entry['page']}, found on page {number}")
        rows = result[number].split("\n")
        rows[index] = f"{'#' * entry['level']} {rows[index].strip()}"
        result[number] = "\n".join(rows)
    return result, moved


def require_missed_entry(pages: dict[int, str], entry: dict) -> None:
    if entry["level"] not in MISSED_LEVELS:
        raise WorkflowError("outline_level", f"missed heading on page {entry['page']} has level {entry['level']!r}, allowed are 1 to 4")
    if entry["page"] not in pages:
        raise WorkflowError("missed_heading_not_found", f"missed heading on page {entry['page']}, which does not exist")


def missed_row(pages: dict[int, str], entry: dict) -> tuple[int, int]:
    named = matching_rows(pages[entry["page"]], entry["line"])
    if len(named) == 1:
        return entry["page"], named[0]
    elsewhere = [(number, index) for number in sorted(pages) if number != entry["page"] for index in matching_rows(pages[number], entry["line"])]
    if named or len(elsewhere) != 1:
        raise WorkflowError(
            "missed_heading_not_found",
            f"page {entry['page']}: the line {entry['line']!r} occurs {len(named)} times in {page_md(entry['page'])} and "
            f"{len(elsewhere)} times in the other page files, it must occur once in {page_md(entry['page'])} or, absent there, "
            "once in the other page files",
        )
    return elsewhere[0]


def matching_rows(text: str, line: str) -> list[int]:
    return [index for index, row in enumerate(text.split("\n")) if row.rstrip() == line.rstrip()]


def require_no_repair_started(batch_dir: Path, pages: dict[int, str]) -> None:
    for number in pages:
        fixed, outlined = batch_dir / fixed_page_md(number), batch_dir / outlined_md(number)
        if fixed.is_file() and not (outlined.is_file() and fixed.read_text(encoding="utf-8") == prefilled(outlined.read_text(encoding="utf-8"))):
            raise WorkflowError(
                "page_repair_started",
                f"{fixed_page_md(number)} differs from its pre-filled form, a page worker has edited it and apply-outline would discard the edits",
            )


def prefilled(text: str) -> str:
    return f"{REPAIR_PENDING}\n\n{text}"


def write_outlined(batch_dir: Path, pages: dict[int, str]) -> None:
    for number, text in pages.items():
        (batch_dir / outlined_md(number)).write_text(text, encoding="utf-8")
        (batch_dir / fixed_page_md(number)).write_text(prefilled(text), encoding="utf-8")


def format_summary(pages: dict[int, str], lines: dict[str, str], missed: list[dict], moved: list[str]) -> str:
    outline = [row for number in sorted(pages) for row in pages[number].split("\n") if row.startswith("#")]
    dropped = sum(1 for line in lines.values() if not line.startswith("#"))
    return "\n".join([
        f"apply-outline ok: {len(lines)} headings, {dropped} set to level 0, {len(missed)} missed headings added",
        "missed headings found on another page than named: " + ("; ".join(moved) or "none"),
        f"pre-filled for the page workers: {fixed_page_md(min(pages))} to {fixed_page_md(max(pages))}, each starting with {REPAIR_PENDING}",
        "outline:",
        *[f"  {row}" for row in outline],
    ])
