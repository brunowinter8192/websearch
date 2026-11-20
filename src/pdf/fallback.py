# INFRASTRUCTURE
from pathlib import Path

from src.pdf.batch_files import REPAIR_PENDING, fixed_page_md, outlined_md, page_png
from src.pdf.manifest import load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.templates import read_template, require_filled, substitute
from src.pdf.worker_outputs import worker_state

FALLBACK_TEMPLATE = "fallback_pages_prompt.md"


# ORCHESTRATOR
def fallback_workflow(batch_dir: str, worker_name: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    worker = require_page_worker(manifest, worker_name)
    pages = missing_pages(batch_path, worker)
    write_prefilled(batch_path, pages)
    prompt = write_fallback_prompt(batch_path, manifest, worker, pages)
    return Report(format_summary(worker, pages, prompt), True)


# FUNCTIONS
def require_page_worker(manifest: dict, worker_name: str) -> dict:
    worker = next((entry for entry in manifest["workers"] if entry["name"] == worker_name), None)
    if worker is None:
        raise WorkflowError("unknown_worker", f"no worker {worker_name!r} in the manifest")
    if "pages" not in worker:
        raise WorkflowError("fallback_not_observed", f"worker {worker_name!r} is no page worker; a block was only observed for page workers")
    return worker


def missing_pages(batch_dir: Path, worker: dict) -> list[int]:
    _, missing = worker_state(batch_dir, worker)
    first, last = worker["pages"]
    pages = [number for number in range(first, last + 1) if fixed_page_md(number) in missing]
    if not pages:
        raise WorkflowError("nothing_missing", f"worker {worker['name']!r} has written every page file, there is nothing to fall back for")
    for number in pages:
        if (batch_dir / fixed_page_md(number)).exists():
            raise WorkflowError("fallback_started", f"{fixed_page_md(number)} already exists as a pre-filled file, a fallback ran before for this page")
        if not (batch_dir / outlined_md(number)).is_file():
            raise WorkflowError("outline_not_applied", f"{outlined_md(number)} does not exist, run pdf apply-outline first")
    return pages


def write_prefilled(batch_dir: Path, pages: list[int]) -> None:
    for number in pages:
        outlined = (batch_dir / outlined_md(number)).read_text(encoding="utf-8")
        (batch_dir / fixed_page_md(number)).write_text(f"{REPAIR_PENDING}\n\n{outlined}", encoding="utf-8")


def write_fallback_prompt(batch_dir: Path, manifest: dict, worker: dict, pages: list[int]) -> Path:
    values = {
        "PDF": manifest["pdf"],
        "PAGES": ", ".join(str(number) for number in pages),
        "PNG_PATTERN": str(batch_dir / page_png("N")),
        "FIXED_PATTERN": str(batch_dir / fixed_page_md("N")),
        "PENDING": REPAIR_PENDING,
    }
    path = batch_dir / f"prompt_fallback_{worker['name']}.md"
    path.write_text(require_filled(substitute(read_template(FALLBACK_TEMPLATE), values)), encoding="utf-8")
    return path


def format_summary(worker: dict, pages: list[int], prompt: Path) -> str:
    return "\n".join([
        f"fallback ok: {worker['name']}",
        "pre-filled from the outlined pages: " + " ".join(fixed_page_md(number) for number in pages),
        f"each starts with {REPAIR_PENDING}; status counts a page as done once its fallback worker removed that line",
        f"prompt: {prompt}",
    ])
