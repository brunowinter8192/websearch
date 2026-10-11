# INFRASTRUCTURE
import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path

import psutil
from liteparse import LiteParse

from src.config import CONTENT_CHECK_THRESHOLD, MANIFEST_FILE_NAME, PROJECT_ROOT
from src.pdf.conversion_log import append_record, count_earlier_attempts, log_failure, new_run_id
from src.pdf.pdf_text import latin_char_counts, pdf_page_count, pdftotext_range
from src.pdf.report import Report, WorkflowError
from src.scraper.scrape_logger import utc_timestamp

PDF_MODELS_PATH = PROJECT_ROOT / "config" / "pdf_models.json"
PROMPT_DIR = Path(__file__).parent / "prompts"
PROMPT_FILES = ("worker_prompt.md", "steps_single.md", "steps_split.md")
CLEANED_PATTERNS = ("anchor_*.md", "prompt_*.md", "batch_*.md", "part*_*.md", MANIFEST_FILE_NAME)
CONVERTER_NAME = "liteparse"
BATCH_PAGES = 40
READ_PAGES_LIMIT = 20
MIN_TEXT_CHARS_PER_PAGE = 100
BYTES_PER_GB = 1024 ** 3
WORKER_RAM_GB = 1.0
RAM_RESERVE_GB = 8.0
MAX_PARALLEL_WORKERS = 20
SHA_CHUNK_BYTES = 1024 * 1024


# ORCHESTRATOR
def extract_workflow(pdf: str, batch_dir: str) -> Report:
    pdf_path = require_pdf(pdf)
    run = open_run(pdf_path)
    return extract_logged(run, pdf_path, Path(batch_dir))


# FUNCTIONS
def require_pdf(pdf: str) -> Path:
    path = Path(pdf).resolve()
    if not path.is_file():
        raise WorkflowError("pdf_not_found", f"PDF not found: {path}")
    return path


def open_run(pdf: Path) -> dict:
    pages = pdf_page_count(pdf)
    available_bytes = current_available_bytes()
    pdf_sha256 = file_sha256(pdf)
    config = build_config()
    record = {
        "record_type": "start",
        "run_id": new_run_id(),
        "ts_start": utc_timestamp(),
        "pdf": str(pdf),
        "pdf_sha256": pdf_sha256,
        "pages": pages,
        "converter": CONVERTER_NAME,
        "converter_version": version(CONVERTER_NAME),
        "config_hash": hash_config(config),
        "config": config,
        "attempt": count_earlier_attempts(pdf_sha256) + 1,
        "available_gb": round(available_bytes / BYTES_PER_GB, 1),
        "workers": worker_limit(available_bytes, len(plan_batches(pages))),
    }
    append_record(record)
    return record


def current_available_bytes() -> int:
    return psutil.virtual_memory().available


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(SHA_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_config() -> dict:
    return {
        "batch_pages": BATCH_PAGES,
        "ocr": False,
        "worker_model": read_worker_model(),
        "prompt_sha": prompt_sha(),
        "threshold": CONTENT_CHECK_THRESHOLD,
        "min_text_chars_per_page": MIN_TEXT_CHARS_PER_PAGE,
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


def plan_batches(pages: int) -> list[tuple[int, int]]:
    return [(first, min(first + BATCH_PAGES - 1, pages)) for first in range(1, pages + 1, BATCH_PAGES)]


def worker_limit(available_bytes: int, batch_count: int) -> int:
    by_ram = math.floor((available_bytes / BYTES_PER_GB - RAM_RESERVE_GB) / WORKER_RAM_GB)
    return max(1, min(MAX_PARALLEL_WORKERS, batch_count, by_ram))


def extract_logged(run: dict, pdf: Path, batch_dir: Path) -> Report:
    try:
        return extract_batches(run, pdf, batch_dir)
    except Exception as error:
        failure_class = log_failure(run["run_id"], run["ts_start"], error, "extract_error")
        return Report(f"extract FAILED ({failure_class}): {error}", False)


def extract_batches(run: dict, pdf: Path, batch_dir: Path) -> Report:
    require_text_layer(pdf, run["pages"])
    prepare_batch_dir(batch_dir)
    page_markdown = parse_pages(pdf, run["pages"])
    batches = plan_batches(run["pages"])
    entries = [write_batch_files(pdf, batch_dir, first, last, page_markdown) for first, last in batches]
    write_manifest(run, pdf, batch_dir, entries)
    return Report(format_summary(run, batch_dir, entries), True)


def require_text_layer(pdf: Path, pages: int) -> None:
    chars = sum(latin_char_counts(pdftotext_range(pdf, 1, pages)).values())
    per_page = chars / pages
    if per_page < MIN_TEXT_CHARS_PER_PAGE:
        raise WorkflowError(
            "no_text_layer",
            f"{pdf.name} has {per_page:.0f} text characters per page, minimum is {MIN_TEXT_CHARS_PER_PAGE}",
        )


def prepare_batch_dir(batch_dir: Path) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    for pattern in CLEANED_PATTERNS:
        for stale in batch_dir.glob(pattern):
            stale.unlink()


def parse_pages(pdf: Path, pages: int) -> dict[int, str]:
    parser = LiteParse(ocr_enabled=False, quiet=True, output_format="markdown", max_pages=pages)
    result = parser.parse(pdf)
    markdown = {page.page_num: page.markdown or "" for page in result.pages}
    if sorted(markdown) != list(range(1, pages + 1)):
        raise WorkflowError("page_count_mismatch", f"liteparse returned {len(markdown)} pages, pdfinfo reports {pages}")
    return markdown


def write_batch_files(pdf: Path, batch_dir: Path, first: int, last: int, page_markdown: dict[int, str]) -> dict:
    entry = batch_entry(first, last)
    (batch_dir / entry["anchor"]).write_text(build_anchor(first, last, page_markdown), encoding="utf-8")
    (batch_dir / entry["prompt"]).write_text(render_prompt(pdf, batch_dir, entry), encoding="utf-8")
    return entry


def batch_entry(first: int, last: int) -> dict:
    span = f"{first}-{last}"
    return {
        "from": first,
        "to": last,
        "anchor": f"anchor_{span}.md",
        "prompt": f"prompt_{span}.md",
        "output": f"batch_{span}.md",
        "part_1": f"part1_{span}.md",
        "part_2": f"part2_{span}.md",
    }


def build_anchor(first: int, last: int, page_markdown: dict[int, str]) -> str:
    pages = [f"<!-- page {number} -->\n\n{page_markdown[number].strip()}\n" for number in range(first, last + 1)]
    return "\n".join(pages)


def render_prompt(pdf: Path, batch_dir: Path, entry: dict) -> str:
    first, last = entry["from"], entry["to"]
    split = last - first + 1 > READ_PAGES_LIMIT
    steps = read_template("steps_split.md" if split else "steps_single.md")
    text = read_template("worker_prompt.md").replace("{{STEPS}}", steps)
    values = {
        "PDF": str(pdf),
        "FROM": str(first),
        "TO": str(last),
        "ANCHOR": str(batch_dir / entry["anchor"]),
        "OUTPUT": str(batch_dir / entry["output"]),
        "PART_1": str(batch_dir / entry["part_1"]),
        "PART_2": str(batch_dir / entry["part_2"]),
        "READ_PAGES": page_range(first, last),
        "READ_PAGES_1": page_range(first, first + READ_PAGES_LIMIT - 1),
        "READ_PAGES_2": page_range(first + READ_PAGES_LIMIT, last),
    }
    return fill_placeholders(text, values)


def read_template(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def page_range(first: int, last: int) -> str:
    return str(first) if first == last else f"{first}-{last}"


def fill_placeholders(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        raise WorkflowError("prompt_placeholder", "worker prompt template has an unfilled placeholder")
    return text


def write_manifest(run: dict, pdf: Path, batch_dir: Path, entries: list[dict]) -> None:
    manifest = {
        "run_id": run["run_id"],
        "ts_start": run["ts_start"],
        "pdf": str(pdf),
        "stem": pdf.stem,
        "pages": run["pages"],
        "batch_pages": BATCH_PAGES,
        "workers": run["workers"],
        "available_gb": run["available_gb"],
        "worker_model": run["config"]["worker_model"],
        "batches": entries,
    }
    (batch_dir / MANIFEST_FILE_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def format_summary(run: dict, batch_dir: Path, entries: list[dict]) -> str:
    lines = [
        f"extract ok: {Path(run['pdf']).stem}",
        f"pages={run['pages']} batches={len(entries)} workers={run['workers']} available_gb={run['available_gb']}",
        f"batch dir: {batch_dir}",
        f"manifest: {batch_dir / MANIFEST_FILE_NAME}",
        "prompts: " + " ".join(entry["prompt"] for entry in entries),
    ]
    return "\n".join(lines)
