# INFRASTRUCTURE
import re
from collections import Counter
from pathlib import Path

from src.config import NEW_PARAGRAPH
from src.pdf.batch_files import (
    BARE_PAGE_NUMBER, KIND_FIGURE, KIND_TABLE, PLACEHOLDER, fixed_page_md, outlined_md, placeholders, region_fixed,
)
from src.pdf.conversion_log import append_record, build_end_record, log_failure
from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import load_runs, page_marker
from src.pdf.worker_outputs import STATE_COMPLETE, format_unfinished, worker_states

PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
FOOTNOTE_DEFINITION = re.compile(r"^\[\^[^\]]+\]:")
TRAILING_FOOTNOTE_MARKS = re.compile(r"(\[\^[^\]]+\])+$")
HYPHENATED_END = re.compile(r"[^\W\d_]-$")
HEADING_LINE_MARKS = re.compile(r"^(#+)", re.MULTILINE)
CLOSING_CHARS = "”’\"')]»*_"
SENTENCE_END_CHARS = ".!?:;"
QUOTE_PAIRS = (("‘‘", "“"), ("’’", "”"))
TARGET_BODY = "body"
TARGET_FOOTNOTE = "footnote"


# ORCHESTRATOR
def assemble_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    require_no_sampling(batch_path)
    return assemble_logged(manifest, batch_path)


# FUNCTIONS
def require_no_sampling(batch_dir: Path) -> None:
    if load_runs(batch_dir):
        raise WorkflowError("sampling_started", "sampling has started, a new assemble would discard its corrections")


def assemble_logged(manifest: dict, batch_dir: Path) -> Report:
    try:
        return assemble_book(manifest, batch_dir)
    except Exception as error:
        failure_class = log_failure(manifest["run_id"], manifest["ts_start"], error, "assemble_error")
        return Report(f"assemble FAILED ({failure_class}): {error}", False)


def assemble_book(manifest: dict, batch_dir: Path) -> Report:
    unfinished = [entry for entry in worker_states(batch_dir, manifest) if entry[1] != STATE_COMPLETE]
    if unfinished:
        return report_unfinished(manifest, unfinished)
    pages = load_pages(batch_dir, manifest["pages"])
    joins = join_pages(pages)
    target = book_path(batch_dir, manifest)
    target.write_text(render_book(batch_dir, pages), encoding="utf-8")
    return Report(format_summary(manifest, target, joins), True)


def report_unfinished(manifest: dict, unfinished: list[tuple[dict, str, list[str]]]) -> Report:
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], "failed", "incomplete_worker",
        incomplete_workers=[{"name": worker["name"], "missing": missing} for worker, _, missing in unfinished],
    ))
    lines = [f"assemble FAILED (incomplete_worker): {len(unfinished)} of {len(manifest['workers'])} workers incomplete, nothing written"]
    return Report("\n".join(lines + format_unfinished(unfinished)), False)


def load_pages(batch_dir: Path, pages: int) -> list[list[str]]:
    loaded = []
    for number in range(1, pages + 1):
        outlined = batch_dir / outlined_md(number)
        if not outlined.is_file():
            raise WorkflowError("outline_not_applied", f"{outlined} does not exist, run pdf apply-outline first")
        fixed = (batch_dir / fixed_page_md(number)).read_text(encoding="utf-8")
        outlined_text = outlined.read_text(encoding="utf-8")
        require_placeholders_kept(number, outlined_text, fixed)
        require_heading_marks_kept(number, outlined_text, fixed)
        loaded.append(paragraphs_of(fixed))
    return loaded


def require_placeholders_kept(number: int, outlined: str, fixed: str) -> None:
    expected, found = Counter(placeholders(outlined)), Counter(placeholders(fixed))
    if expected != found:
        lost = " ".join(f"{kind} {name}" for kind, name in (expected - found))
        added = " ".join(f"{kind} {name}" for kind, name in (found - expected))
        raise WorkflowError(
            "placeholder_changed",
            f"page {number}: {fixed_page_md(number)} lost placeholders [{lost}] and has extra placeholders [{added}]",
        )


def require_heading_marks_kept(number: int, outlined: str, fixed: str) -> None:
    expected, found = HEADING_LINE_MARKS.findall(outlined), HEADING_LINE_MARKS.findall(fixed)
    if expected != found:
        raise WorkflowError(
            "heading_marks_changed",
            f"page {number}: {fixed_page_md(number)} has heading marks {found}, {outlined_md(number)} has {expected}",
        )


def paragraphs_of(text: str) -> list[str]:
    blocks = PARAGRAPH_BREAK.split(text.strip())
    return [cleaned for cleaned in ("\n".join(line.rstrip() for line in block.strip("\n").split("\n")) for block in blocks) if cleaned]


def join_pages(pages: list[list[str]]) -> list[tuple[int, int, str]]:
    joins = []
    for index in range(len(pages)):
        while True:
            target = open_target(index + 1, pages[index])
            found = continuation(pages, index + 1) if target else None
            if found is None:
                break
            kind, position = target
            page_index, paragraph_index = found
            pages[index][position] = joined(pages[index][position], pages[page_index].pop(paragraph_index))
            joins.append((index + 1, page_index + 1, kind))
    return joins


def open_target(number: int, paragraphs: list[str]) -> tuple[str, int] | None:
    body = [index for index in range(len(paragraphs)) if is_body(paragraphs, index)]
    notes = [index for index, paragraph in enumerate(paragraphs) if FOOTNOTE_DEFINITION.match(paragraph)]
    open_body = bool(body) and not terminated(paragraphs[body[-1]])
    open_note = bool(notes) and not terminated(paragraphs[notes[-1]])
    if open_body and open_note:
        raise WorkflowError("ambiguous_page_join", f"page {number}: its last paragraph and its last footnote both run on")
    if open_body:
        return TARGET_BODY, body[-1]
    if open_note:
        return TARGET_FOOTNOTE, notes[-1]
    return None


def is_body(paragraphs: list[str], index: int) -> bool:
    paragraph = paragraphs[index]
    return not (paragraph.startswith("#") or FOOTNOTE_DEFINITION.match(paragraph) or skippable(paragraphs, index))


def skippable(paragraphs: list[str], index: int) -> bool:
    if paragraphs[index].startswith("#") or FOOTNOTE_DEFINITION.match(paragraphs[index]):
        return False
    if region_kind(paragraphs[index]) or BARE_PAGE_NUMBER.fullmatch(paragraphs[index]):
        return True
    before = region_kind(paragraphs[index - 1]) if index > 0 else None
    after = region_kind(paragraphs[index + 1]) if index + 1 < len(paragraphs) else None
    return before in (KIND_TABLE, KIND_FIGURE) or after == KIND_TABLE


def region_kind(paragraph: str) -> str | None:
    match = PLACEHOLDER.fullmatch(paragraph)
    return match[1] if match else None


def terminated(paragraph: str) -> bool:
    text = TRAILING_FOOTNOTE_MARKS.sub("", paragraph.rstrip()).rstrip(CLOSING_CHARS)
    return bool(text) and text[-1] in SENTENCE_END_CHARS


def continuation(pages: list[list[str]], start: int) -> tuple[int, int] | None:
    for page_index in range(start, len(pages)):
        paragraphs = pages[page_index]
        for index, paragraph in enumerate(paragraphs):
            if paragraph.startswith("#") or FOOTNOTE_DEFINITION.match(paragraph):
                return None
            if not skippable(paragraphs, index):
                return page_index, index
    return None


def joined(head: str, tail: str) -> str:
    head = head.rstrip()
    if HYPHENATED_END.search(head):
        return head[:-1] + tail.lstrip()
    return f"{head} {tail.lstrip()}"


def render_book(batch_dir: Path, pages: list[list[str]]) -> str:
    sections = []
    for number, paragraphs in enumerate(pages, start=1):
        body = [region_text(batch_dir, paragraph) for paragraph in paragraphs]
        sections.append(NEW_PARAGRAPH.join([page_marker(number), *body]))
    text = NEW_PARAGRAPH.join(sections) + "\n"
    for printed, typographic in QUOTE_PAIRS:
        text = text.replace(printed, typographic)
    return text


def region_text(batch_dir: Path, paragraph: str) -> str:
    match = PLACEHOLDER.fullmatch(paragraph)
    if not match:
        return paragraph
    return NEW_PARAGRAPH.join(paragraphs_of((batch_dir / region_fixed(match[1], match[2])).read_text(encoding="utf-8")))


def format_summary(manifest: dict, target: Path, joins: list[tuple[int, int, str]]) -> str:
    described = " ".join(f"{first}->{second}({kind})" for first, second, kind in joins) or "none"
    return "\n".join([
        f"assemble ok: {target}",
        f"pages={manifest['pages']} tables={len(manifest['tables'])} figures={len(manifest['figures'])} "
        f"formulas={len(manifest.get('formulas', []))}",
        f"page joins: {len(joins)}: {described}",
    ])
