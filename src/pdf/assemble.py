# INFRASTRUCTURE
import json
import os
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config import (
    CONTENT_CHECK_THRESHOLD, CONTROL_FILE_NAME, MANIFEST_FILE_NAME, MODE_SCAN, OUTLIER_PAGE_FACTOR, PARAGRAPH_LIMIT_BYTES,
)
from src.pdf.conversion_log import append_record, build_end_record, log_failure
from src.pdf.pdf_text import latin_char_counts, pdftotext_pages
from src.pdf.report import Report, WorkflowError

MIN_REFERENCE_CHARS = 200
FAILED_STATUSES = ("missing_file", "low_recall")
CONTROL_FAILURE_CLASSES = {
    "control_missing": "failed",
    "control_incomplete": "failed",
    "control_grave": "content_check_failed",
}
PARAGRAPH_SEPARATOR = re.compile(r"(\n{2,})")
SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+(?=\S)")
TABLE_RULE_CHARS = set("-: ")
NEW_PARAGRAPH = "\n\n"


# ORCHESTRATOR
def assemble_workflow(batch_dir: str, out_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    return assemble_logged(manifest, batch_path, Path(out_dir))


# FUNCTIONS
@dataclass(frozen=True)
class BatchResult:
    first: int
    last: int
    status: str
    recall: float | None
    ref_chars: int
    out_chars: int
    unjudged_pages: tuple[int, ...] = ()


@dataclass(frozen=True)
class ControlResult:
    status: str
    checked: tuple[int, ...]
    missing: tuple[int, ...]
    grave: tuple[tuple[int, str, str], ...]
    minor: tuple[tuple[int, str, str], ...]


@dataclass(frozen=True)
class SplitResult:
    text: str
    paragraphs_split: int
    tables_split: int
    paragraphs_over_limit: int


def load_manifest(batch_dir: Path) -> dict:
    path = batch_dir / MANIFEST_FILE_NAME
    if not path.is_file():
        raise WorkflowError("manifest_missing", f"no {MANIFEST_FILE_NAME} in {batch_dir}, run extract first")
    return json.loads(path.read_text(encoding="utf-8"))


def assemble_logged(manifest: dict, batch_dir: Path, out_dir: Path) -> Report:
    try:
        return assemble_batches(manifest, batch_dir, out_dir)
    except Exception as error:
        failure_class = log_failure(manifest["run_id"], manifest["ts_start"], error, "assemble_error")
        return Report(f"assemble FAILED ({failure_class}): {error}", False)


def assemble_batches(manifest: dict, batch_dir: Path, out_dir: Path) -> Report:
    scan = manifest.get("mode") == MODE_SCAN
    results = [check_batch(Path(manifest["pdf"]), batch_dir, batch, scan) for batch in ordered_batches(manifest)]
    failed = [result for result in results if result.status in FAILED_STATUSES]
    control = check_control(manifest, batch_dir) if scan else None
    if failed or (control is not None and control.status != "ok"):
        return report_failure(manifest, results, failed, control)
    return write_book(manifest, batch_dir, out_dir, results, control)


def ordered_batches(manifest: dict) -> list[dict]:
    return sorted(manifest["batches"], key=lambda batch: batch["from"])


def check_batch(pdf: Path, batch_dir: Path, batch: dict, scan: bool = False) -> BatchResult:
    first, last = batch["from"], batch["to"]
    reference, outliers = (Counter(), ()) if scan else judged_reference(reference_pages(pdf, first, last))
    ref_chars = sum(reference.values())
    output = batch_dir / batch["output"]
    if not output.is_file():
        return BatchResult(first, last, "missing_file", None, ref_chars, 0, outliers)
    produced = latin_char_counts(output.read_text(encoding="utf-8"))
    out_chars = sum(produced.values())
    if scan:
        return BatchResult(first, last, "ok", None, 0, out_chars)
    if ref_chars < MIN_REFERENCE_CHARS:
        return BatchResult(first, last, "unjudged", None, ref_chars, out_chars, outliers)
    recall = sum(min(count, produced.get(char, 0)) for char, count in reference.items()) / ref_chars
    status = "ok" if recall >= CONTENT_CHECK_THRESHOLD else "low_recall"
    return BatchResult(first, last, status, recall, ref_chars, out_chars, outliers)


def reference_pages(pdf: Path, first: int, last: int) -> dict[int, Counter]:
    texts = pdftotext_pages(pdf, first, last)
    return {first + offset: latin_char_counts(text) for offset, text in enumerate(texts)}


def judged_reference(pages: dict[int, Counter]) -> tuple[Counter, tuple[int, ...]]:
    sizes = {number: sum(counts.values()) for number, counts in pages.items()}
    median = statistics.median(sizes.values())
    outliers = tuple(number for number, size in sizes.items() if median > 0 and size > OUTLIER_PAGE_FACTOR * median)
    reference: Counter = Counter()
    for number, counts in pages.items():
        if number not in outliers:
            reference.update(counts)
    return reference, outliers


def check_control(manifest: dict, batch_dir: Path) -> ControlResult:
    drawn = tuple(manifest["control_pages"])
    path = batch_dir / CONTROL_FILE_NAME
    if not path.is_file():
        return ControlResult("control_missing", (), drawn, (), ())
    pages = parse_control(path)
    checked = tuple(sorted(pages))
    missing = tuple(page for page in drawn if page not in pages)
    findings = [finding for page in checked for finding in control_findings(page, pages[page])]
    grave = tuple(finding for finding in findings if finding[2] == "grave")
    minor = tuple(finding for finding in findings if finding[2] == "minor")
    status = "control_incomplete" if missing else "control_grave" if grave else "ok"
    return ControlResult(status, checked, missing, grave, minor)


def parse_control(path: Path) -> dict[int, dict]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["pages"]
        return {int(entry["page"]): entry for entry in entries}
    except (ValueError, KeyError, TypeError) as error:
        raise WorkflowError("control_unreadable", f"{path} is not the expected control JSON: {error}") from error


def control_findings(page: int, entry: dict) -> list[tuple[int, str, str]]:
    return [
        (page, f"{finding.get('kind', 'other')}: {finding.get('detail', '')}", "grave" if finding.get("grave") else "minor")
        for finding in entry.get("findings", [])
    ]


def report_failure(manifest: dict, results: list[BatchResult], failed: list[BatchResult], control: ControlResult | None) -> Report:
    outcome, failure_class = classify_failure(failed, control)
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], outcome, failure_class,
        failed_batches=[failed_batch_entry(result) for result in failed],
        **totals(results), **control_fields(manifest, control),
    ))
    lines = [f"assemble FAILED ({failure_class}): {len(failed)} of {len(results)} batches, nothing written"]
    lines += [describe_failure(result) for result in failed]
    lines += describe_unjudged_pages(results)
    lines += describe_control(control)
    return Report("\n".join(lines), False)


def classify_failure(failed: list[BatchResult], control: ControlResult | None) -> tuple[str, str]:
    if any(result.status == "missing_file" for result in failed):
        return "failed", "missing_batch"
    if failed:
        return "content_check_failed", "low_recall"
    return CONTROL_FAILURE_CLASSES[control.status], control.status


def failed_batch_entry(result: BatchResult) -> dict:
    recall = None if result.recall is None else round(result.recall, 4)
    return {"from": result.first, "to": result.last, "reason": result.status, "recall": recall}


def describe_failure(result: BatchResult) -> str:
    span = f"batch {result.first}-{result.last}"
    if result.recall is None:
        return f"  {span}: {result.status}"
    return f"  {span}: {result.status} recall={result.recall:.3f} threshold={CONTENT_CHECK_THRESHOLD}"


def totals(results: list[BatchResult]) -> dict:
    chars_out = sum(result.out_chars for result in results)
    chars_ref = sum(result.ref_chars for result in results)
    return {
        "chars_out": chars_out,
        "chars_ref": chars_ref,
        "char_ratio": round(chars_out / chars_ref, 4) if chars_ref else None,
        "unjudged_pages": [number for result in results for number in result.unjudged_pages],
    }


def control_fields(manifest: dict, control: ControlResult | None) -> dict:
    if control is None:
        return {}
    return {
        "control_pages": manifest["control_pages"],
        "control_checked": list(control.checked),
        "control_missing": list(control.missing),
        "control_grave": sorted({page for page, _, _ in control.grave}),
        "control_minor": sorted({page for page, _, _ in control.minor}),
    }


def describe_control(control: ControlResult | None) -> list[str]:
    if control is None:
        return []
    if control.status == "control_missing":
        return [f"control: {CONTROL_FILE_NAME} missing, drawn pages " + " ".join(str(page) for page in control.missing)]
    lines = [f"control: {len(control.checked)} pages checked, {len(control.grave)} grave and {len(control.minor)} minor findings"]
    if control.missing:
        lines.append("control pages missing in control.json: " + " ".join(str(page) for page in control.missing))
    lines += [f"  page {page} grave: {text}" for page, text, _ in control.grave]
    lines += [f"  page {page} minor: {text}" for page, text, _ in control.minor]
    return lines


def write_book(manifest: dict, batch_dir: Path, out_dir: Path, results: list[BatchResult], control: ControlResult | None) -> Report:
    split = split_long_paragraphs(join_batches(manifest, batch_dir))
    target = out_dir / f"{manifest['stem']}.md"
    write_atomically(target, split.text + "\n")
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], "ok", None,
        md=str(target), **totals(results), **split_counts(split), **control_fields(manifest, control),
    ))
    return Report(format_success(manifest, target, results, split, control), True)


def join_batches(manifest: dict, batch_dir: Path) -> str:
    texts = [(batch_dir / batch["output"]).read_text(encoding="utf-8").strip() for batch in ordered_batches(manifest)]
    return NEW_PARAGRAPH.join(texts)


def split_long_paragraphs(book: str) -> SplitResult:
    parts = PARAGRAPH_SEPARATOR.split(book)
    pieces = [split_paragraph(paragraph) for paragraph in parts[0::2]]
    rebuilt = [NEW_PARAGRAPH.join(chunks) for chunks in pieces]
    text = "".join(part for pair in zip(rebuilt, parts[1::2] + [""]) for part in pair)
    split = [(paragraph, chunks) for paragraph, chunks in zip(parts[0::2], pieces) if len(chunks) > 1]
    return SplitResult(
        text=text,
        paragraphs_split=len(split),
        tables_split=sum(1 for paragraph, _ in split if is_table(paragraph)),
        paragraphs_over_limit=sum(1 for chunks in pieces for chunk in chunks if size(chunk) > PARAGRAPH_LIMIT_BYTES),
    )


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def is_table(paragraph: str) -> bool:
    return paragraph.lstrip().startswith("|")


def split_paragraph(paragraph: str) -> list[str]:
    if size(paragraph) <= PARAGRAPH_LIMIT_BYTES:
        return [paragraph]
    if is_table(paragraph):
        return split_table(paragraph)
    return split_block(paragraph)


def split_table(paragraph: str) -> list[str]:
    lines = paragraph.split("\n")
    has_rule = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= TABLE_RULE_CHARS
    head = lines[:2] if has_rule else []
    blocks, current = [], list(head)
    for row in lines[len(head):]:
        if size("\n".join(current + [row])) > PARAGRAPH_LIMIT_BYTES and len(current) > len(head):
            blocks.append("\n".join(current))
            current = list(head)
        current.append(row)
    blocks.append("\n".join(current))
    return blocks


def split_block(paragraph: str) -> list[str]:
    lines = paragraph.split("\n")
    if len(lines) == 1:
        return split_line(paragraph)
    pieces = [piece for line in lines for piece in split_line(line)]
    return pack(pieces, "\n")


def split_line(line: str) -> list[str]:
    if size(line) <= PARAGRAPH_LIMIT_BYTES:
        return [line]
    sentences = []
    for sentence in SENTENCE_END.split(line):
        sentences += pack(sentence.split(" "), " ") if size(sentence) > PARAGRAPH_LIMIT_BYTES else [sentence]
    return pack(sentences, " ")


def pack(pieces: list[str], joiner: str) -> list[str]:
    chunks, current = [], ""
    for piece in pieces:
        candidate = f"{current}{joiner}{piece}" if current else piece
        if size(candidate) > PARAGRAPH_LIMIT_BYTES and current:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    chunks.append(current)
    return chunks


def split_counts(split: SplitResult) -> dict:
    return {
        "paragraphs_split": split.paragraphs_split,
        "tables_split": split.tables_split,
        "paragraphs_over_limit": split.paragraphs_over_limit,
    }


def write_atomically(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, target)


def format_success(manifest: dict, target: Path, results: list[BatchResult], split: SplitResult, control: ControlResult | None) -> str:
    lines = [f"assemble ok: {target}"]
    lines += describe_control(control) if control is not None else describe_recall(manifest, results)
    lines.append(describe_split(split))
    return "\n".join(lines)


def describe_recall(manifest: dict, results: list[BatchResult]) -> list[str]:
    judged = [result for result in results if result.recall is not None]
    unjudged = [result for result in results if result.status == "unjudged"]
    lowest = min(judged, key=lambda result: result.recall)
    lines = [f"batches={len(results)} pages={manifest['pages']} lowest recall={lowest.recall:.3f} at {lowest.first}-{lowest.last}"]
    if unjudged:
        lines.append("unjudged batches (too little reference text): " + " ".join(f"{r.first}-{r.last}" for r in unjudged))
    lines += describe_unjudged_pages(results)
    return lines


def describe_split(split: SplitResult) -> str:
    return (
        f"paragraphs split: {split.paragraphs_split} (tables: {split.tables_split}), "
        f"limit {PARAGRAPH_LIMIT_BYTES} bytes, left over the limit: {split.paragraphs_over_limit}"
    )


def describe_unjudged_pages(results: list[BatchResult]) -> list[str]:
    pages = [number for result in results for number in result.unjudged_pages]
    if not pages:
        return []
    label = f"unjudged pages (text layer over {OUTLIER_PAGE_FACTOR}x the median page of the batch): "
    return [label + " ".join(str(number) for number in pages)]
