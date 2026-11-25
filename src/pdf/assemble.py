# INFRASTRUCTURE
import re
from collections import Counter
from pathlib import Path

from src.config import NEW_PARAGRAPH
from src.pdf.batch_files import (
    BARE_PAGE_NUMBER, KIND_FIGURE, KIND_TABLE, PLACEHOLDER, fixed_page_md, outlined_md, placeholders, region_fixed, region_missing,
)
from src.pdf.conversion_log import append_record, build_end_record, log_failure
from src.pdf.coverage import normalized, tokens_of
from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import load_runs, page_marker
from src.pdf.worker_outputs import STATE_COMPLETE, format_unfinished, worker_states

PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
FOOTNOTE_DEFINITION = re.compile(r"^\[\^[^\]]+\]:")
TRAILING_FOOTNOTE_MARKS = re.compile(r"(\[\^[^\]]+\])+$")
HYPHENATED_END = re.compile(r"[^\W\d_]-$")
EMAIL_END = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+$")
URL_END = re.compile(r"(https?://|www\.)\S+$")
CITATION_END = re.compile(r"\([A-Z][^()]*\b\d{4}[a-z]?\)[*_]*$")
BOLD_ONLY = re.compile(r"\*\*.*\*\*", re.DOTALL)
HEADING_LINE_MARKS = re.compile(r"^(#+)", re.MULTILINE)
LIST_ITEM = re.compile(r"^(- |\(\d+\) |([a-z]|[ivxl]+)\) )")
CONTINUATION_MARK = re.compile(r"^(- |> )")
TRAILING_TAGS = re.compile(r"(</?[a-zA-Z][^<>]*>)+$")
CAPTION_LABEL = re.compile(r"^\**(Table|TABLE|Fig\.|Figure|FIGURE) \d+(\.|—|\*| \(|$)")
BARE_CAPTION_LABEL = re.compile(r"\**(Table|Fig\.|Figure) \d+\**")
TABLE_NOTE_START = re.compile(r"^[A-Z(]")
UPPERCASE_START = re.compile(r"^[A-Z]")
TABLE_MARK_NOTE = re.compile(r"^\[\^[^\]\d]+\]:")
TABLE_NOTE_LABEL = re.compile(r"^[*_]+[A-Z]\w*[*_]+:")
PICTURE_TEXT_MARKUP = re.compile(r"<!-- (Start|End) of picture text -->|<br>")
BRACKETED_LINE = re.compile(r"\[[^\]^]+\]")
IMPRINT_MARKS = ("ISSN", "©", "downloaded from IP address")
BOX_QUOTE = ">"
EMPHASIS_CHARS = "*_"
CLOSING_CHARS = "”’‖\"')]»*_"
SENTENCE_END_CHARS = ".!?:"
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
    require_region_words(batch_dir, manifest)
    pages = load_pages(batch_dir, manifest["pages"])
    joins = join_pages(pages, {normalized(span) for span in manifest.get("running", [])})
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


def require_region_words(batch_dir: Path, manifest: dict) -> None:
    for kind, key in ((KIND_TABLE, "tables"), (KIND_FIGURE, "figures")):
        for region_id in manifest[key]:
            listed = batch_dir / region_missing(kind, region_id)
            if not listed.is_file():
                continue
            fixed = "".join(tokens_of([(batch_dir / region_fixed(kind, region_id)).read_text(encoding="utf-8")]))
            absent = [word for word in listed.read_text(encoding="utf-8").split() if normalized(word) not in fixed]
            if absent:
                raise WorkflowError(
                    "region_word_missing",
                    f"{region_fixed(kind, region_id)} lacks words printed in the region and listed in "
                    f"{region_missing(kind, region_id)}: {' '.join(absent)}",
                )


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
    if sorted(expected) != sorted(found):
        raise WorkflowError(
            "heading_marks_changed",
            f"page {number}: {fixed_page_md(number)} has heading marks {found}, {outlined_md(number)} has {expected}",
        )


def paragraphs_of(text: str) -> list[str]:
    blocks = PARAGRAPH_BREAK.split(text.strip())
    return [cleaned for cleaned in ("\n".join(line.rstrip() for line in block.strip("\n").split("\n")) for block in blocks) if cleaned]


def join_pages(pages: list[list[str]], running: set[str]) -> list[tuple[int, int, str]]:
    joins = []
    for index in range(len(pages)):
        while True:
            targets = open_targets(pages[index], running if index == 0 else set())
            found = first_continuation(pages, index + 1, targets)
            if found is None or new_list_item(pages, index, targets[0], found):
                break
            planned = planned_joins(pages, index + 1, targets, found)
            for (kind, position), (page_index, paragraph_index) in reversed(planned):
                pages[index][position] = joined(pages[index][position], pages[page_index].pop(paragraph_index))
            joins += [(index + 1, page_index + 1, kind) for (kind, _), (page_index, _) in planned]
    return joins


def open_targets(paragraphs: list[str], running: set[str]) -> list[tuple[str, int]]:
    area = footnote_area(paragraphs)
    body = [
        index for index in range(len(paragraphs))
        if index not in area and is_body(paragraphs, index) and normalized(paragraphs[index]) not in running
    ]
    targets = []
    if body and not terminated(paragraphs[body[-1]]):
        targets.append((TARGET_BODY, body[-1]))
    if area and not terminated(paragraphs[area[-1]]):
        targets.append((TARGET_FOOTNOTE, area[-1]))
    return targets


def footnote_area(paragraphs: list[str]) -> list[int]:
    area, inside = [], False
    for index, paragraph in enumerate(paragraphs):
        if paragraph.startswith("#"):
            inside = False
        elif footnote_definition(paragraphs, index):
            inside = True
        if inside:
            area.append(index)
    return area


def footnote_definition(paragraphs: list[str], index: int) -> bool:
    return bool(FOOTNOTE_DEFINITION.match(paragraphs[index])) and not table_note(paragraphs, index)


def table_note(paragraphs: list[str], index: int) -> bool:
    if index == 0:
        return False
    paragraph, before = paragraphs[index], paragraphs[index - 1]
    note_form = bool(TABLE_MARK_NOTE.match(paragraph) or TABLE_NOTE_LABEL.match(paragraph))
    if region_kind(before) == KIND_TABLE:
        return note_form or (bool(TABLE_NOTE_START.match(paragraph)) and not text_flow_after_table(paragraphs, index))
    return note_form and bool(TABLE_MARK_NOTE.match(before)) and table_note(paragraphs, index - 1)


def text_flow_after_table(paragraphs: list[str], index: int) -> bool:
    if not UPPERCASE_START.match(paragraphs[index]):
        return False
    after = index + 1
    return after == len(paragraphs) or (bool(UPPERCASE_START.match(paragraphs[after])) and is_body(paragraphs, after))


def first_continuation(pages: list[list[str]], start: int, targets: list[tuple[str, int]]) -> tuple[int, int] | None:
    if not targets:
        return None
    if targets[0][0] == TARGET_BODY:
        return continuation(pages, start)
    if start >= len(pages):
        return None
    note = footnote_candidate(start, pages[start], -1, True)
    if note is not None:
        return start, note
    found = continuation(pages, start)
    return found if found and runs_on(pages[found[0]][found[1]]) else None


def footnote_candidate(number: int, paragraphs: list[str], after: int, alone: bool) -> int | None:
    first_note = next((index for index in range(len(paragraphs)) if footnote_definition(paragraphs, index)), None)
    if first_note is None:
        return next((index for index in range(after + 1, len(paragraphs)) if stranded_note_text(paragraphs, index)), None)
    candidate = first_note - 1
    if candidate <= after:
        return None
    if not footnote_text(paragraphs, candidate):
        raise WorkflowError(
            "ambiguous_page_join", f"page {number}: its last footnote runs on, but page {number + 1} has no text before its first footnote",
        )
    return candidate if runs_on(paragraphs[candidate]) or not alone else None


def stranded_note_text(paragraphs: list[str], index: int) -> bool:
    if not footnote_text(paragraphs, index):
        return False
    after_open_body = index > 0 and is_body(paragraphs, index - 1) and not terminated(paragraphs[index - 1])
    return runs_on(paragraphs[index]) or after_open_body


def runs_on(paragraph: str) -> bool:
    text = CONTINUATION_MARK.sub("", paragraph, count=1).lstrip()
    return bool(text) and text[0].islower()


def new_list_item(pages: list[list[str]], index: int, target: tuple[str, int], found: tuple[int, int]) -> bool:
    page_index, paragraph_index = found
    return bool(LIST_ITEM.match(pages[index][target[1]]) and LIST_ITEM.match(pages[page_index][paragraph_index]))


def planned_joins(
    pages: list[list[str]], number: int, targets: list[tuple[str, int]], found: tuple[int, int],
) -> list[tuple[tuple[str, int], tuple[int, int]]]:
    note = footnote_candidate(number, pages[found[0]], found[1], False) if len(targets) == 2 and found[0] == number else None
    return [(targets[0], found)] + ([(targets[1], (found[0], note))] if note is not None else [])


def footnote_text(paragraphs: list[str], index: int) -> bool:
    return is_body(paragraphs, index) or paragraphs[index].startswith(BOX_QUOTE)


def is_body(paragraphs: list[str], index: int) -> bool:
    paragraph = paragraphs[index]
    return not (paragraph.startswith("#") or footnote_definition(paragraphs, index) or skippable(paragraphs, index))


def skippable(paragraphs: list[str], index: int) -> bool:
    paragraph = paragraphs[index]
    if paragraph.startswith("#") or footnote_definition(paragraphs, index):
        return False
    if region_kind(paragraph) or page_number(paragraph) or imprint(paragraph) or CAPTION_LABEL.match(paragraph):
        return True
    before = paragraphs[index - 1] if index > 0 else ""
    if BARE_CAPTION_LABEL.fullmatch(before) or (region_kind(before) == KIND_FIGURE and not runs_on(paragraph)):
        return True
    return table_note(paragraphs, index)


def region_kind(paragraph: str) -> str | None:
    match = PLACEHOLDER.fullmatch(paragraph)
    return match[1] if match else None


def page_number(paragraph: str) -> bool:
    return bool(BARE_PAGE_NUMBER.fullmatch(PICTURE_TEXT_MARKUP.sub("", paragraph).strip().strip(EMPHASIS_CHARS)))


def imprint(paragraph: str) -> bool:
    if paragraph.startswith(BOX_QUOTE) or BRACKETED_LINE.fullmatch(paragraph):
        return True
    return any(mark in paragraph for mark in IMPRINT_MARKS)


def terminated(paragraph: str) -> bool:
    if BOLD_ONLY.fullmatch(paragraph.strip()) or CITATION_END.search(paragraph.rstrip()):
        return True
    text = TRAILING_FOOTNOTE_MARKS.sub("", TRAILING_TAGS.sub("", paragraph.rstrip()).rstrip()).rstrip(CLOSING_CHARS)
    return bool(text) and (text[-1] in SENTENCE_END_CHARS or bool(EMAIL_END.search(text) or URL_END.search(text)))


def continuation(pages: list[list[str]], start: int) -> tuple[int, int] | None:
    for page_index in range(start, len(pages)):
        paragraphs = pages[page_index]
        area = footnote_area(paragraphs)
        if area and all(index in area or skippable(paragraphs, index) for index in range(len(paragraphs))):
            continue
        for index, paragraph in enumerate(paragraphs):
            if paragraph.startswith("#") or footnote_definition(paragraphs, index):
                return None
            if not skippable(paragraphs, index):
                return page_index, index
    return None


def joined(head: str, tail: str) -> str:
    head, tail = head.rstrip(), CONTINUATION_MARK.sub("", tail.lstrip(), count=1)
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
