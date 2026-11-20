# INFRASTRUCTURE
import hashlib
import json
import re
from pathlib import Path

from src.config import SAMPLES_DIR_NAME
from src.pdf.report import WorkflowError

RUN_FILE_NAME = "run.json"
FINDINGS_FILE_NAME = "findings.md"
RUN_DIR_PREFIX = "run_"
STATUS_OPEN = "open"
PAGE_MARKER = re.compile(r"^<!-- page (\d+) -->$", re.MULTILINE)


# FUNCTIONS
def page_marker(number: int) -> str:
    return f"<!-- page {number} -->"


def page_markers(text: str) -> list[tuple[int, int]]:
    return [(int(match[1]), match.start()) for match in PAGE_MARKER.finditer(text)]


def run_dir(batch_dir: Path, number: int) -> Path:
    return batch_dir / SAMPLES_DIR_NAME / f"{RUN_DIR_PREFIX}{number}"


def load_runs(batch_dir: Path) -> list[dict]:
    root = batch_dir / SAMPLES_DIR_NAME
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in root.glob(f"{RUN_DIR_PREFIX}*/{RUN_FILE_NAME}")]
    return sorted(runs, key=lambda run: run["run"])


def write_run(batch_dir: Path, run: dict) -> None:
    (run_dir(batch_dir, run["run"]) / RUN_FILE_NAME).write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")


def sampled_pages(runs: list[dict]) -> set[int]:
    return {page for run in runs for page in run["pages"]}


def loop_ended(runs: list[dict], pages: int) -> bool:
    if not runs or runs[-1]["status"] == STATUS_OPEN:
        return False
    return not runs[-1]["applied"] or len(sampled_pages(runs)) == pages


def open_run_of(runs: list[dict]) -> dict:
    if not runs or runs[-1]["status"] != STATUS_OPEN:
        raise WorkflowError("no_open_run", "no open sample run, open one with pdf sample")
    return runs[-1]


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def findings_path(batch_dir: Path, run: dict) -> Path:
    return run_dir(batch_dir, run["run"]) / FINDINGS_FILE_NAME


def changed_excerpts(batch_dir: Path, run: dict) -> list[tuple[dict, str]]:
    changed = []
    for excerpt in run["excerpts"]:
        path = run_dir(batch_dir, run["run"]) / excerpt["file"]
        if not path.is_file():
            raise WorkflowError("excerpt_missing", f"excerpt file {path} is missing")
        edited = path.read_text(encoding="utf-8")
        if is_changed(excerpt, edited):
            changed.append((excerpt, edited))
    return changed


def is_changed(excerpt: dict, edited: str) -> bool:
    return edited.rstrip() != excerpt["original"].rstrip()


def markers_kept(excerpt: dict, edited: str) -> bool:
    return [page for page, _ in page_markers(edited)] == [page for page, _ in page_markers(excerpt["original"])]
