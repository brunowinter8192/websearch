# INFRASTRUCTURE
import difflib
from pathlib import Path

from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report
from src.pdf.sample_duplicates import KIND_DUPLICATE, KIND_MIXED, judge_excerpts
from src.pdf.sample_runs import (
    changed_excerpts, findings_path, load_runs, markers_kept, merge_part_findings, open_run_of, run_dir,
)

REPORT_FILE_NAME = "report.md"
FENCE = "````"
CONTEXT_LINES = 2


# ORCHESTRATOR
def sample_report_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    run = open_run_of(load_runs(batch_path))
    book = book_path(batch_path, manifest).read_text(encoding="utf-8")
    judged = judge_excerpts(book, changed_excerpts(batch_path, run))
    merge_part_findings(batch_path, run)
    findings = read_findings(findings_path(batch_path, run))
    target = write_report(batch_path, run, build_report(run, findings, judged))
    return Report(format_summary(run, findings, judged, target), True)


# FUNCTIONS
def read_findings(path: Path) -> str | None:
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def build_report(run: dict, findings: str | None, judged: list[tuple[dict, str, str, list[int]]]) -> str:
    lines = [
        f"# Sample run {run['run']}",
        "",
        "Pages sampled: " + " ".join(str(page) for page in run["pages"]),
        "",
        "## Findings of the sampling worker",
        "",
        findings if findings is not None else "findings.md does not exist",
        "",
        "## Corrections",
        "",
        f"Each change is shown with {CONTEXT_LINES} unchanged lines before and after it.",
        "",
    ]
    if not judged:
        lines += ["none", ""]
    for excerpt, edited, kind, sources in judged:
        lines += describe_correction(excerpt, edited, kind, sources)
    return "\n".join(lines)


def describe_correction(excerpt: dict, edited: str, kind: str, sources: list[int]) -> list[str]:
    pages = " ".join(str(page) for page in excerpt["pages"])
    lines = [f"### Pages {pages} ({excerpt['file']})", ""]
    if not markers_kept(excerpt, edited):
        lines += ["WARNING: the page marker lines of this excerpt were changed", ""]
    lines += duplicate_note(kind, sources)
    before_lines = excerpt["original"].rstrip().split("\n")
    after_lines = edited.rstrip().split("\n")
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag != "equal":
            before = before_lines[max(a_start - CONTEXT_LINES, 0):a_end + CONTEXT_LINES]
            after = after_lines[max(b_start - CONTEXT_LINES, 0):b_end + CONTEXT_LINES]
            lines += ["before:", "", FENCE, *before, FENCE, "", "after:", "", FENCE, *after, FENCE, ""]
    return lines


def duplicate_note(kind: str, sources: list[int]) -> list[str]:
    pages = " ".join(str(page) for page in sources)
    if kind == KIND_DUPLICATE:
        return [f"DUPLICATE: the inserted text already ends a paragraph on page {pages}, before this excerpt. sample-close rejects this correction.", ""]
    if kind == KIND_MIXED:
        return [
            f"WARNING: an inserted text already ends a paragraph on page {pages}, before this excerpt, and the excerpt has other changes. "
            "sample-close refuses until this page is rejected or the inserted text is removed from the excerpt.",
            "",
        ]
    return []


def write_report(batch_dir: Path, run: dict, text: str) -> Path:
    target = run_dir(batch_dir, run["run"]) / REPORT_FILE_NAME
    target.write_text(text + "\n", encoding="utf-8")
    return target


def format_summary(run: dict, findings: str | None, judged: list[tuple[dict, str, str, list[int]]], target: Path) -> str:
    corrected = " ".join(str(page) for excerpt, _, _, _ in judged for page in excerpt["pages"]) or "none"
    duplicates = " ".join(excerpt["file"] for excerpt, _, kind, _ in judged if kind == KIND_DUPLICATE) or "none"
    mixed = " ".join(excerpt["file"] for excerpt, _, kind, _ in judged if kind == KIND_MIXED) or "none"
    return "\n".join([
        f"sample run {run['run']} report: {target}",
        "pages sampled: " + " ".join(str(page) for page in run["pages"]),
        f"findings file: {'present' if findings is not None else 'missing'}",
        f"corrected excerpts: {len(judged)} (pages {corrected})",
        f"duplicates of earlier text, rejected at close: {duplicates}",
        f"duplicates mixed with other changes, close refuses: {mixed}",
    ])
