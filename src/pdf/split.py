# INFRASTRUCTURE
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from src.config import (
    BLOCKED_DIR_NAME, MANIFEST_FILE_NAME, PARAGRAPH_LIMIT_BYTES, PIECE_PAGES, PROJECT_ROOT, RESPLIT_PIECE_PAGES, SAMPLE_SHARE,
    SAMPLES_DIR_NAME,
)
from src.pdf.conversion_log import append_record, count_earlier_attempts, log_failure, new_run_id
from src.pdf.manifest import book_path, write_manifest
from src.pdf.pieces import plan_ranges, write_piece_prompt
from src.pdf.report import Report, WorkflowError
from src.pdf.templates import PROMPT_DIR
from src.scraper.scrape_logger import utc_timestamp

PDF_MODELS_PATH = PROJECT_ROOT / "config" / "pdf_models.json"
PROMPT_FILES = (
    "worker_prompt.md", "steps_single.md", "steps_split.md", "chunk_steps.md",
    "sample_prompt.md", "sample_excerpt_steps.md",
)
CLEANED_PATTERNS = ("prompt_*.md", "piece_*.md", "part*_*.md", MANIFEST_FILE_NAME)
PAGES_LINE = re.compile(r"^Pages:\s+(\d+)\s*$", re.MULTILINE)
PARALLEL_WORKERS = 20
SHA_CHUNK_BYTES = 1024 * 1024


# ORCHESTRATOR
def split_workflow(pdf: str, batch_dir: str) -> Report:
    pdf_path = require_pdf(pdf)
    run = open_run(pdf_path)
    return split_logged(run, pdf_path, Path(batch_dir))


# FUNCTIONS
def require_pdf(pdf: str) -> Path:
    path = Path(pdf).resolve()
    if not path.is_file():
        raise WorkflowError("pdf_not_found", f"PDF not found: {path}")
    return path


def open_run(pdf: Path) -> dict:
    pdf_sha256 = file_sha256(pdf)
    config = build_config()
    record = {
        "record_type": "start",
        "run_id": new_run_id(),
        "ts_start": utc_timestamp(),
        "pdf": str(pdf),
        "pdf_sha256": pdf_sha256,
        "pages": pdf_page_count(pdf),
        "config_hash": hash_config(config),
        "config": config,
        "attempt": count_earlier_attempts(pdf_sha256) + 1,
    }
    append_record(record)
    return record


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(SHA_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(pdf: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, check=True)
    match = PAGES_LINE.search(result.stdout.decode("utf-8", errors="replace"))
    if match is None:
        raise WorkflowError("unreadable_pdf", f"pdfinfo reports no page count for {pdf}")
    return int(match.group(1))


def build_config() -> dict:
    return {
        "piece_pages": PIECE_PAGES,
        "resplit_piece_pages": list(RESPLIT_PIECE_PAGES),
        "workers": PARALLEL_WORKERS,
        "worker_model": read_worker_model(),
        "prompt_sha": prompt_sha(),
        "sample_share": SAMPLE_SHARE,
        "paragraph_limit_bytes": PARAGRAPH_LIMIT_BYTES,
    }


def read_worker_model() -> str:
    return json.loads(PDF_MODELS_PATH.read_text(encoding="utf-8"))["worker"]


def prompt_sha() -> str:
    digest = hashlib.sha256()
    for name in PROMPT_FILES:
        digest.update((PROMPT_DIR / name).read_bytes())
    return digest.hexdigest()[:16]


def hash_config(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def split_logged(run: dict, pdf: Path, batch_dir: Path) -> Report:
    try:
        return split_pieces(run, pdf, batch_dir)
    except Exception as error:
        failure_class = log_failure(run["run_id"], run["ts_start"], error, "split_error")
        return Report(f"split FAILED ({failure_class}): {error}", False)


def split_pieces(run: dict, pdf: Path, batch_dir: Path) -> Report:
    manifest = build_manifest(run, pdf)
    prepare_batch_dir(batch_dir, manifest)
    manifest["pieces"] = [write_piece_prompt(pdf, batch_dir, first, last) for first, last in plan_ranges(1, run["pages"], PIECE_PAGES)]
    write_manifest(batch_dir, manifest)
    return Report(format_summary(manifest, batch_dir), True)


def build_manifest(run: dict, pdf: Path) -> dict:
    return {
        "run_id": run["run_id"],
        "ts_start": run["ts_start"],
        "pdf": str(pdf),
        "pdf_sha256": run["pdf_sha256"],
        "stem": pdf.stem,
        "pages": run["pages"],
        "piece_pages": PIECE_PAGES,
        "workers": run["config"]["workers"],
        "worker_model": run["config"]["worker_model"],
        "pieces": [],
    }


def prepare_batch_dir(batch_dir: Path, manifest: dict) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    for pattern in CLEANED_PATTERNS:
        for stale in batch_dir.glob(pattern):
            stale.unlink()
    book_path(batch_dir, manifest).unlink(missing_ok=True)
    shutil.rmtree(batch_dir / SAMPLES_DIR_NAME, ignore_errors=True)
    shutil.rmtree(batch_dir / BLOCKED_DIR_NAME, ignore_errors=True)


def format_summary(manifest: dict, batch_dir: Path) -> str:
    return "\n".join([
        f"split ok: {manifest['stem']}",
        f"pages={manifest['pages']} pieces={len(manifest['pieces'])} workers={manifest['workers']}",
        f"batch dir: {batch_dir}",
        f"manifest: {batch_dir / MANIFEST_FILE_NAME}",
        "prompts: " + " ".join(piece["prompt"] for piece in manifest["pieces"]),
    ])
