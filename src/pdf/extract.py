# INFRASTRUCTURE
import hashlib
import json
import math
import random
from importlib.metadata import version
from pathlib import Path

from liteparse import LiteParse

from src.config import (
    CONTENT_CHECK_THRESHOLD, CONTROL_FILE_NAME, CONTROL_PROMPT_NAME, MANIFEST_FILE_NAME, MODE_SCAN, MODE_TEXT,
    OUTLIER_PAGE_FACTOR, PARAGRAPH_LIMIT_BYTES, PROJECT_ROOT,
)
from src.pdf.conversion_log import append_record, count_earlier_attempts, log_failure, new_run_id
from src.pdf.pdf_text import latin_char_counts, pdf_page_count, pdftotext_range
from src.pdf.report import Report, WorkflowError
from src.scraper.scrape_logger import utc_timestamp

PDF_MODELS_PATH = PROJECT_ROOT / "config" / "pdf_models.json"
PROMPT_DIR = Path(__file__).parent / "prompts"
PROMPT_FILES = (
    "worker_prompt.md", "steps_single.md", "steps_split.md", "chunk_steps.md",
    "scan_worker_prompt.md", "scan_steps_single.md", "scan_steps_split.md",
    "control_prompt.md", "control_page_steps.md",
)
CLEANED_PATTERNS = ("anchor_*.md", "prompt_*.md", "batch_*.md", "part*_*.md", MANIFEST_FILE_NAME, CONTROL_FILE_NAME)
CONVERTER_NAME = "liteparse"
BATCH_PAGES = 50
READ_PAGES_LIMIT = 20
PARALLEL_WORKERS = 20
MIN_TEXT_CHARS_PER_PAGE = 100
CONTROL_SHARE = 0.10
SHA_CHUNK_BYTES = 1024 * 1024
TEMPLATES = {
    MODE_TEXT: {"prompt": "worker_prompt.md", "single": "steps_single.md", "split": "steps_split.md", "first_step": 2},
    MODE_SCAN: {"prompt": "scan_worker_prompt.md", "single": "scan_steps_single.md", "split": "scan_steps_split.md", "first_step": 1},
}


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
    pdf_sha256 = file_sha256(pdf)
    config = build_config()
    record = {
        "record_type": "start",
        "run_id": new_run_id(),
        "ts_start": utc_timestamp(),
        "pdf": str(pdf),
        "pdf_sha256": pdf_sha256,
        "pages": pages,
        "mode": decide_mode(pdf, pages),
        "converter": CONVERTER_NAME,
        "converter_version": version(CONVERTER_NAME),
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


def decide_mode(pdf: Path, pages: int) -> str:
    chars = sum(latin_char_counts(pdftotext_range(pdf, 1, pages)).values())
    return MODE_TEXT if chars / pages >= MIN_TEXT_CHARS_PER_PAGE else MODE_SCAN


def build_config() -> dict:
    return {
        "batch_pages": BATCH_PAGES,
        "workers": PARALLEL_WORKERS,
        "ocr": False,
        "worker_model": read_worker_model(),
        "prompt_sha": prompt_sha(),
        "threshold": CONTENT_CHECK_THRESHOLD,
        "outlier_page_factor": OUTLIER_PAGE_FACTOR,
        "paragraph_limit_bytes": PARAGRAPH_LIMIT_BYTES,
        "min_text_chars_per_page": MIN_TEXT_CHARS_PER_PAGE,
        "control_share": CONTROL_SHARE,
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
    prepare_batch_dir(batch_dir)
    batches = plan_batches(run["pages"])
    if run["mode"] == MODE_TEXT:
        page_markdown = parse_pages(pdf, run["pages"])
        entries = [write_text_batch_files(pdf, batch_dir, first, last, page_markdown) for first, last in batches]
        control_pages = None
    else:
        entries = [write_scan_batch_files(pdf, batch_dir, first, last) for first, last in batches]
        control_pages = draw_control_pages(batches, run["pdf_sha256"])
        write_control_prompt(pdf, batch_dir, entries, control_pages)
    write_manifest(run, pdf, batch_dir, entries, control_pages)
    return Report(format_summary(run, batch_dir, entries, control_pages), True)


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


def write_text_batch_files(pdf: Path, batch_dir: Path, first: int, last: int, page_markdown: dict[int, str]) -> dict:
    entry = batch_entry(first, last, MODE_TEXT)
    (batch_dir / entry["anchor"]).write_text(build_anchor(first, last, page_markdown), encoding="utf-8")
    (batch_dir / entry["prompt"]).write_text(render_prompt(pdf, batch_dir, entry, MODE_TEXT), encoding="utf-8")
    return entry


def write_scan_batch_files(pdf: Path, batch_dir: Path, first: int, last: int) -> dict:
    entry = batch_entry(first, last, MODE_SCAN)
    (batch_dir / entry["prompt"]).write_text(render_prompt(pdf, batch_dir, entry, MODE_SCAN), encoding="utf-8")
    return entry


def batch_entry(first: int, last: int, mode: str = MODE_TEXT) -> dict:
    span = f"{first}-{last}"
    chunks = read_chunks(first, last)
    return {
        "from": first,
        "to": last,
        "anchor": f"anchor_{span}.md" if mode == MODE_TEXT else None,
        "prompt": f"prompt_{span}.md",
        "output": f"batch_{span}.md",
        "parts": [f"part{number}_{span}.md" for number in range(1, len(chunks) + 1)] if len(chunks) > 1 else [],
    }


def read_chunks(first: int, last: int) -> list[tuple[int, int]]:
    return [(start, min(start + READ_PAGES_LIMIT - 1, last)) for start in range(first, last + 1, READ_PAGES_LIMIT)]


def build_anchor(first: int, last: int, page_markdown: dict[int, str]) -> str:
    pages = [f"<!-- page {number} -->\n\n{page_markdown[number].strip()}\n" for number in range(first, last + 1)]
    return "\n".join(pages)


def render_prompt(pdf: Path, batch_dir: Path, entry: dict, mode: str = MODE_TEXT) -> str:
    first, last = entry["from"], entry["to"]
    templates = TEMPLATES[mode]
    text = read_template(templates["prompt"]).replace("{{STEPS}}", build_steps(batch_dir, entry, templates))
    values = {
        "PDF": str(pdf),
        "FROM": str(first),
        "TO": str(last),
        "ANCHOR": str(batch_dir / entry["anchor"]) if entry["anchor"] else "",
        "OUTPUT": str(batch_dir / entry["output"]),
        "READ_PAGES": page_range(first, last),
    }
    return require_filled(substitute(text, values))


def build_steps(batch_dir: Path, entry: dict, templates: dict) -> str:
    if not entry["parts"]:
        return read_template(templates["single"])
    first_step = templates["first_step"]
    chunks = read_chunks(entry["from"], entry["to"])
    parts = [str(batch_dir / name) for name in entry["parts"]]
    blocks = [chunk_block(first_step + 2 * number, chunk, part) for number, (chunk, part) in enumerate(zip(chunks, parts))]
    next_number = first_step + 2 * len(chunks)
    values = {
        "CHUNK_STEPS": "\n".join(blocks),
        "CAT_NUMBER": str(next_number),
        "CAT_COMMAND": cat_command(parts, str(batch_dir / entry["output"])),
        "DONE_NUMBER": str(next_number + 1),
    }
    return substitute(read_template(templates["split"]), values)


def chunk_block(read_number: int, chunk: tuple[int, int], part: str) -> str:
    values = {
        "READ_NUMBER": str(read_number),
        "WRITE_NUMBER": str(read_number + 1),
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


def draw_control_pages(batches: list[tuple[int, int]], seed: str) -> list[int]:
    rng = random.Random(seed)
    drawn = []
    for first, last in batches:
        count = math.ceil(CONTROL_SHARE * (last - first + 1))
        drawn += rng.sample(range(first, last + 1), count)
    return sorted(drawn)


def write_control_prompt(pdf: Path, batch_dir: Path, entries: list[dict], control_pages: list[int]) -> None:
    (batch_dir / CONTROL_PROMPT_NAME).write_text(render_control_prompt(pdf, batch_dir, entries, control_pages), encoding="utf-8")


def render_control_prompt(pdf: Path, batch_dir: Path, entries: list[dict], control_pages: list[int]) -> str:
    batch_files = [str(batch_dir / entry["output"]) for entry in entries if any(entry["from"] <= page <= entry["to"] for page in control_pages)]
    page_steps = [control_page_block(2 + index, page, batch_dir / batch_of(entries, page)["output"]) for index, page in enumerate(control_pages)]
    values = {
        "PDF": str(pdf),
        "CONTROL_PAGES": " ".join(str(page) for page in control_pages),
        "BATCH_FILES": " ".join(batch_files),
        "OUTPUT": str(batch_dir / CONTROL_FILE_NAME),
        "PAGE_STEPS": "\n".join(page_steps),
        "WRITE_NUMBER": str(2 + len(control_pages)),
        "DONE_NUMBER": str(3 + len(control_pages)),
    }
    return require_filled(substitute(read_template("control_prompt.md"), values))


def batch_of(entries: list[dict], page: int) -> dict:
    return next(entry for entry in entries if entry["from"] <= page <= entry["to"])


def control_page_block(step_number: int, page: int, batch_file: Path) -> str:
    values = {"STEP_NUMBER": str(step_number), "PAGE": str(page), "BATCH_FILE": str(batch_file)}
    return substitute(read_template("control_page_steps.md").rstrip("\n"), values)


def write_manifest(run: dict, pdf: Path, batch_dir: Path, entries: list[dict], control_pages: list[int] | None) -> None:
    manifest = {
        "run_id": run["run_id"],
        "ts_start": run["ts_start"],
        "pdf": str(pdf),
        "stem": pdf.stem,
        "pages": run["pages"],
        "mode": run["mode"],
        "batch_pages": BATCH_PAGES,
        "workers": run["config"]["workers"],
        "worker_model": run["config"]["worker_model"],
        "batches": entries,
    }
    if control_pages is not None:
        manifest["control_pages"] = control_pages
    (batch_dir / MANIFEST_FILE_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def format_summary(run: dict, batch_dir: Path, entries: list[dict], control_pages: list[int] | None) -> str:
    lines = [
        f"extract ok: {Path(run['pdf']).stem}",
        f"mode={run['mode']} pages={run['pages']} batches={len(entries)} workers={run['config']['workers']}",
        f"batch dir: {batch_dir}",
        f"manifest: {batch_dir / MANIFEST_FILE_NAME}",
        "prompts: " + " ".join(entry["prompt"] for entry in entries),
    ]
    if control_pages is not None:
        lines.append(f"control prompt: {CONTROL_PROMPT_NAME} control pages: " + " ".join(str(page) for page in control_pages))
    return "\n".join(lines)
