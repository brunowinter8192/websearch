# INFRASTRUCTURE
import json
import os
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config import CONTENT_CHECK_THRESHOLD, MANIFEST_FILE_NAME, OUTLIER_PAGE_FACTOR
from src.pdf.conversion_log import append_record, build_end_record, log_failure
from src.pdf.pdf_text import latin_char_counts, pdftotext_pages
from src.pdf.report import Report, WorkflowError

MIN_REFERENCE_CHARS = 200
FAILED_STATUSES = ("missing_file", "low_recall")


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
    results = [check_batch(Path(manifest["pdf"]), batch_dir, batch) for batch in ordered_batches(manifest)]
    failed = [result for result in results if result.status in FAILED_STATUSES]
    if failed:
        return report_failure(manifest, results, failed)
    return write_book(manifest, batch_dir, out_dir, results)


def ordered_batches(manifest: dict) -> list[dict]:
    return sorted(manifest["batches"], key=lambda batch: batch["from"])


def check_batch(pdf: Path, batch_dir: Path, batch: dict) -> BatchResult:
    first, last = batch["from"], batch["to"]
    reference, outliers = judged_reference(reference_pages(pdf, first, last))
    ref_chars = sum(reference.values())
    output = batch_dir / batch["output"]
    if not output.is_file():
        return BatchResult(first, last, "missing_file", None, ref_chars, 0, outliers)
    produced = latin_char_counts(output.read_text(encoding="utf-8"))
    out_chars = sum(produced.values())
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


def report_failure(manifest: dict, results: list[BatchResult], failed: list[BatchResult]) -> Report:
    outcome, failure_class = classify_failure(failed)
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], outcome, failure_class,
        failed_batches=[failed_batch_entry(result) for result in failed],
        **totals(results),
    ))
    lines = [f"assemble FAILED ({failure_class}): {len(failed)} of {len(results)} batches, nothing written"]
    lines += [describe_failure(result) for result in failed]
    lines += describe_unjudged_pages(results)
    return Report("\n".join(lines), False)


def classify_failure(failed: list[BatchResult]) -> tuple[str, str]:
    if any(result.status == "missing_file" for result in failed):
        return "failed", "missing_batch"
    return "content_check_failed", "low_recall"


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


def write_book(manifest: dict, batch_dir: Path, out_dir: Path, results: list[BatchResult]) -> Report:
    texts = [(batch_dir / batch["output"]).read_text(encoding="utf-8").strip() for batch in ordered_batches(manifest)]
    target = out_dir / f"{manifest['stem']}.md"
    write_atomically(target, "\n\n".join(texts) + "\n")
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], "ok", None,
        md=str(target), **totals(results),
    ))
    return Report(format_success(manifest, target, results), True)


def write_atomically(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, target)


def format_success(manifest: dict, target: Path, results: list[BatchResult]) -> str:
    judged = [result for result in results if result.recall is not None]
    unjudged = [result for result in results if result.status == "unjudged"]
    lowest = min(judged, key=lambda result: result.recall)
    lines = [
        f"assemble ok: {target}",
        f"batches={len(results)} pages={manifest['pages']} lowest recall={lowest.recall:.3f} at {lowest.first}-{lowest.last}",
    ]
    if unjudged:
        lines.append("unjudged batches (too little reference text): " + " ".join(f"{r.first}-{r.last}" for r in unjudged))
    lines += describe_unjudged_pages(results)
    return "\n".join(lines)


def describe_unjudged_pages(results: list[BatchResult]) -> list[str]:
    pages = [number for result in results for number in result.unjudged_pages]
    if not pages:
        return []
    label = f"unjudged pages (text layer over {OUTLIER_PAGE_FACTOR}x the median page of the batch): "
    return [label + " ".join(str(number) for number in pages)]
