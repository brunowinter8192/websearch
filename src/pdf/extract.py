# INFRASTRUCTURE
import hashlib
import json
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
PROMPT_FILES = ("worker_prompt.md", "steps_single.md", "steps_split.md", "chunk_steps.md")
CLEANED_PATTERNS = ("anchor_*.md", "prompt_*.md", "batch_*.md", "part*_*.md", MANIFEST_FILE_NAME)
CONVERTER_NAME = "liteparse"
BATCH_PAGES = 50
READ_PAGES_LIMIT = 20
PARALLEL_WORKERS = 20
WORKER_RAM_GB = 0.8
MIN_AVAILABLE_GB = PARALLEL_WORKERS * WORKER_RAM_GB
MIN_TEXT_CHARS_PER_PAGE = 100
BYTES_PER_GB = 1024 ** 3
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
        "workers": PARALLEL_WORKERS,
        "min_available_gb": MIN_AVAILABLE_GB,
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


def extract_logged(run: dict, pdf: Path, batch_dir: Path) -> Report:
    try:
        return extract_batches(run, pdf, batch_dir)
    except Exception as error:
        failure_class = log_failure(run["run_id"], run["ts_start"], error, "extract_error")
        return Report(f"extract FAILED ({failure_class}): {error}", False)


def extract_batches(run: dict, pdf: Path, batch_dir: Path) -> Report:
    require_free_ram(run["available_gb"])
    require_text_layer(pdf, run["pages"])
    prepare_batch_dir(batch_dir)
    page_markdown = parse_pages(pdf, run["pages"])
    batches = plan_batches(run["pages"])
    entries = [write_batch_files(pdf, batch_dir, first, last, page_markdown) for first, last in batches]
    write_manifest(run, pdf, batch_dir, entries)
    return Report(format_summary(run, batch_dir, entries), True)


def require_free_ram(available_gb: float) -> None:
    if available_gb < MIN_AVAILABLE_GB:
        raise WorkflowError(
            "low_ram",
            f"{available_gb} GB available, {PARALLEL_WORKERS} workers at {WORKER_RAM_GB} GB need {MIN_AVAILABLE_GB:.1f} GB",
        )


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
    chunks = read_chunks(first, last)
    return {
        "from": first,
        "to": last,
        "anchor": f"anchor_{span}.md",
        "prompt": f"prompt_{span}.md",
        "output": f"batch_{span}.md",
        "parts": [f"part{number}_{span}.md" for number in range(1, len(chunks) + 1)] if len(chunks) > 1 else [],
    }


def read_chunks(first: int, last: int) -> list[tuple[int, int]]:
    return [(start, min(start + READ_PAGES_LIMIT - 1, last)) for start in range(first, last + 1, READ_PAGES_LIMIT)]


def build_anchor(first: int, last: int, page_markdown: dict[int, str]) -> str:
    pages = [f"<!-- page {number} -->\n\n{page_markdown[number].strip()}\n" for number in range(first, last + 1)]
    return "\n".join(pages)


def render_prompt(pdf: Path, batch_dir: Path, entry: dict) -> str:
    first, last = entry["from"], entry["to"]
    text = read_template("worker_prompt.md").replace("{{STEPS}}", build_steps(batch_dir, entry))
    values = {
        "PDF": str(pdf),
        "FROM": str(first),
        "TO": str(last),
        "ANCHOR": str(batch_dir / entry["anchor"]),
        "OUTPUT": str(batch_dir / entry["output"]),
        "READ_PAGES": page_range(first, last),
    }
    return require_filled(substitute(text, values))


def build_steps(batch_dir: Path, entry: dict) -> str:
    if not entry["parts"]:
        return read_template("steps_single.md")
    chunks = read_chunks(entry["from"], entry["to"])
    parts = [str(batch_dir / name) for name in entry["parts"]]
    blocks = [chunk_block(number, chunk, part) for number, (chunk, part) in enumerate(zip(chunks, parts))]
    next_number = 2 + 2 * len(chunks)
    values = {
        "CHUNK_STEPS": "\n".join(blocks),
        "CAT_NUMBER": str(next_number),
        "CAT_COMMAND": cat_command(parts, str(batch_dir / entry["output"])),
        "DONE_NUMBER": str(next_number + 1),
    }
    return substitute(read_template("steps_split.md"), values)


def chunk_block(index: int, chunk: tuple[int, int], part: str) -> str:
    values = {
        "READ_NUMBER": str(2 + 2 * index),
        "WRITE_NUMBER": str(3 + 2 * index),
        "CHUNK_PAGES": page_range(*chunk),
        "CHUNK_PART": part,
    }
    return substitute(read_template("chunk_steps.md").rstrip("\n"), values)


def cat_command(parts: list[str], output: str) -> str:
    joined = "; echo; ".join(f'cat "{part}"' for part in parts)
    removals = " ".join(f'"{part}"' for part in parts)
    return f'{{ {joined}; }} > "{output}" && rm {removals}'


def read_template(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def page_range(first: int, last: int) -> str:
    return str(first) if first == last else f"{first}-{last}"


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def require_filled(text: str) -> str:
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
        "workers": run["config"]["workers"],
        "available_gb": run["available_gb"],
        "worker_model": run["config"]["worker_model"],
        "batches": entries,
    }
    (batch_dir / MANIFEST_FILE_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def format_summary(run: dict, batch_dir: Path, entries: list[dict]) -> str:
    lines = [
        f"extract ok: {Path(run['pdf']).stem}",
        f"pages={run['pages']} batches={len(entries)} workers={run['config']['workers']} available_gb={run['available_gb']}",
        f"batch dir: {batch_dir}",
        f"manifest: {batch_dir / MANIFEST_FILE_NAME}",
        "prompts: " + " ".join(entry["prompt"] for entry in entries),
    ]
    return "\n".join(lines)
