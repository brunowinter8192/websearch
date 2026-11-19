# INFRASTRUCTURE
from pathlib import Path

from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import (
    changed_excerpts, findings_path, load_runs, loop_ended, markers_kept, open_run_of, sampled_pages, text_sha, write_run,
)

STATUS_CLOSED = "closed"


# ORCHESTRATOR
def sample_close_workflow(batch_dir: str, rejected_pages: list[int]) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    run = open_run_of(load_runs(batch_path))
    require_findings(findings_path(batch_path, run))
    accepted, rejected = judge_corrections(run, changed_excerpts(batch_path, run), rejected_pages)
    apply_corrections(book_path(batch_path, manifest), run, accepted)
    close_run(batch_path, run, accepted, rejected)
    return Report(format_summary(manifest, run, load_runs(batch_path)), True)


# FUNCTIONS
def require_findings(path: Path) -> None:
    if not path.is_file():
        raise WorkflowError("findings_missing", f"{path} does not exist, the sampling worker is not done")


def judge_corrections(run: dict, changed: list[tuple[dict, str]], rejected_pages: list[int]) -> tuple[list, list]:
    unknown = [page for page in rejected_pages if page not in run["pages"]]
    if unknown:
        raise WorkflowError("reject_unknown_page", f"pages {unknown} were not sampled in run {run['run']}")
    accepted = [(excerpt, edited) for excerpt, edited in changed if not set(excerpt["pages"]) & set(rejected_pages)]
    rejected = [(excerpt, edited) for excerpt, edited in changed if set(excerpt["pages"]) & set(rejected_pages)]
    broken = [excerpt["file"] for excerpt, edited in accepted if not markers_kept(excerpt, edited)]
    if broken:
        raise WorkflowError("excerpt_markers_changed", f"page marker lines changed in {broken}, reject these pages or restore the markers")
    return accepted, rejected


def apply_corrections(book_file: Path, run: dict, accepted: list[tuple[dict, str]]) -> None:
    book = book_file.read_text(encoding="utf-8")
    if text_sha(book) != run["book_sha256"]:
        raise WorkflowError("book_changed", f"{book_file} changed since sample run {run['run']} was opened")
    for excerpt, edited in sorted(accepted, key=lambda item: item[0]["start"], reverse=True):
        original = excerpt["original"]
        trailing = original[len(original.rstrip()):]
        book = book[:excerpt["start"]] + edited.rstrip() + trailing + book[excerpt["end"]:]
    book_file.write_text(book, encoding="utf-8")


def close_run(batch_dir: Path, run: dict, accepted: list[tuple[dict, str]], rejected: list[tuple[dict, str]]) -> None:
    run["status"] = STATUS_CLOSED
    run["applied"] = [excerpt["file"] for excerpt, _ in accepted]
    run["rejected"] = [excerpt["file"] for excerpt, _ in rejected]
    write_run(batch_dir, run)


def format_summary(manifest: dict, run: dict, runs: list[dict]) -> str:
    lines = [
        f"sample run {run['run']} closed: corrections applied {len(run['applied'])}, rejected {len(run['rejected'])}",
        "applied: " + (" ".join(run["applied"]) or "none"),
        "rejected: " + (" ".join(run["rejected"]) or "none"),
        f"pages sampled: {len(sampled_pages(runs))} of {manifest['pages']}",
    ]
    lines.append(loop_state(manifest, run, runs))
    return "\n".join(lines)


def loop_state(manifest: dict, run: dict, runs: list[dict]) -> str:
    if not loop_ended(runs, manifest["pages"]):
        return "loop continues: open the next run with pdf sample"
    if not run["applied"]:
        return f"loop ended: run {run['run']} applied no correction"
    return "loop ended: every page has been sampled"
