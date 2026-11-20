# INFRASTRUCTURE
import contextlib
import hashlib
import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pymupdf
import pymupdf4llm

from src.config import MANIFEST_FILE_NAME, NEW_PARAGRAPH, PARAGRAPH_LIMIT_BYTES, PROJECT_ROOT, SAMPLE_SHARE, SAMPLES_DIR_NAME
from src.pdf.batch_files import (
    BARE_PAGE_NUMBER, BOOKMARKS_FILE, FIGURES_DIR, FORMULAS_DIR, HEADINGS_FILE, HEADINGS_FIXED_FILE, KIND_FIGURE,
    KIND_FORMULA, KIND_HEADING, KIND_TABLE, PAGE_PNG_DIR, PAGES_DIR, TABLES_DIR, WORKER_OUTLINE, fixed_page_md, outlined_md,
    page_md, page_png, placeholder, region_current, region_dir, region_fixed, region_png,
)
from src.pdf.conversion_log import append_record, count_earlier_attempts, log_failure, new_run_id
from src.pdf.coverage import require_coverage
from src.pdf.manifest import book_path, write_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.templates import PROMPT_DIR, read_template, require_filled, substitute
from src.scraper.scrape_logger import utc_timestamp

PDF_MODELS_PATH = PROJECT_ROOT / "config" / "pdf_models.json"
OCR_MODULE = "pymupdf4llm.ocr.rapidocr_api"
OCR_ENGINE = "rapidocr"
CONVERTER_LOG_FILE = "extract_log.txt"
OCR_PAGE_LINE = re.compile(r"^OCR on page\.number=(\d+)/", re.MULTILINE)
PAGE_DPI = 150
REGION_DPI = 200
PAGE_WORKER_PAGES = 5
SHA_CHUNK_BYTES = 1024 * 1024
CLASS_TEXT = "text"
CLASS_TABLE = "table"
CLASS_PICTURE = "picture"
CLASS_HEADING = "section-header"
CLASS_TITLE = "title"
CLASS_FORMULA = "formula"
HEADING_CLASSES = {CLASS_HEADING, CLASS_TITLE}
RUNNING_CLASSES = {"page-header", "page-footer"}
KNOWN_CLASSES = {
    CLASS_TEXT, CLASS_TABLE, CLASS_PICTURE, CLASS_FORMULA, *HEADING_CLASSES, "list-item", "caption", "footnote", *RUNNING_CLASSES,
}
NUMBERED_FORMULA_CLASSES = {CLASS_TEXT, CLASS_HEADING, CLASS_FORMULA}
FORMULA_HEADING_SIGN = "¼"
EQUATION_NUMBER = re.compile(r"ð\d+Þ")
PICTURE_TEXT_MARKUP = re.compile(r"<!-- (Start|End) of picture text -->|<br>")
WORD_CHAR = re.compile(r"\w")
ROW_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES
ROW_TOLERANCE_PT = 2.0
INDENT_MIN_PT = 3.0
INDENT_MAX_PT = 30.0
LEFT_TOLERANCE_PT = 1.0
NEEDLE_WORDS = 3
DIRECTION_TOLERANCE = 0.01
HYPHENATED_END = re.compile(r"[^\W\d_]-$")
MARKUP = "[*_]*"
REGION_DIRS = (TABLES_DIR, FIGURES_DIR, FORMULAS_DIR)
STALE_DIRS = (PAGES_DIR, PAGE_PNG_DIR, *REGION_DIRS, SAMPLES_DIR_NAME)
STALE_FILES = (MANIFEST_FILE_NAME, HEADINGS_FILE, HEADINGS_FIXED_FILE, BOOKMARKS_FILE, CONVERTER_LOG_FILE)
STALE_PATTERNS = ("prompt_*.md",)
WORKER_TABLES = "tables"
WORKER_FIGURES = "figures"
WORKER_FORMULAS = "formulas"
REGION_KINDS = ((KIND_TABLE, "tables"), (KIND_FIGURE, "figures"), (KIND_FORMULA, "formulas"))


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
    pdf_sha256 = file_sha256(pdf)
    config = build_config()
    with pymupdf.open(pdf) as document:
        pages = document.page_count
    record = {
        "record_type": "start",
        "run_id": new_run_id(),
        "ts_start": utc_timestamp(),
        "pdf": str(pdf),
        "pdf_sha256": pdf_sha256,
        "pages": pages,
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


def build_config() -> dict:
    return {
        "converter": f"pymupdf4llm {pymupdf4llm.__version__}",
        "ocr": OCR_ENGINE,
        "page_dpi": PAGE_DPI,
        "region_dpi": REGION_DPI,
        "page_worker_pages": PAGE_WORKER_PAGES,
        "worker_model": read_worker_model(),
        "prompt_sha": prompt_sha(),
        "sample_share": SAMPLE_SHARE,
        "paragraph_limit_bytes": PARAGRAPH_LIMIT_BYTES,
    }


def read_worker_model() -> str:
    return json.loads(PDF_MODELS_PATH.read_text(encoding="utf-8"))["worker"]


def prompt_sha() -> str:
    digest = hashlib.sha256()
    for path in sorted(PROMPT_DIR.glob("*.md")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def hash_config(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def extract_logged(run: dict, pdf: Path, batch_dir: Path) -> Report:
    try:
        return extract_batch(run, pdf, batch_dir)
    except Exception as error:
        failure_class = log_failure(run["run_id"], run["ts_start"], error, "extract_error")
        return Report(f"extract FAILED ({failure_class}): {error}", False)


def extract_batch(run: dict, pdf: Path, batch_dir: Path) -> Report:
    prepare_batch_dir(batch_dir, pdf.stem)
    document = pymupdf.open(pdf)
    chunks = convert(document, batch_dir / CONVERTER_LOG_FILE)
    ocr_pages = read_ocr_pages(batch_dir / CONVERTER_LOG_FILE)
    pages = [build_page(number, chunk, document[number - 1], number in ocr_pages) for number, chunk in enumerate(chunks, start=1)]
    require_coverage(document, pages)
    write_pages(batch_dir, unrotated_original(pdf), pages)
    write_json(batch_dir / BOOKMARKS_FILE, bookmarks(document))
    write_json(batch_dir / HEADINGS_FILE, [heading for page in pages for heading in page["headings"]])
    manifest = build_manifest(run, pdf, pages)
    manifest["workers"] = write_worker_prompts(pdf, batch_dir, manifest)
    write_manifest(batch_dir, manifest)
    return Report(format_summary(manifest, batch_dir, pages, ocr_pages), True)


def prepare_batch_dir(batch_dir: Path, stem: str) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    for name in STALE_DIRS:
        shutil.rmtree(batch_dir / name, ignore_errors=True)
    for name in STALE_FILES:
        (batch_dir / name).unlink(missing_ok=True)
    for pattern in STALE_PATTERNS:
        for stale in batch_dir.glob(pattern):
            stale.unlink()
    book_path(batch_dir, {"stem": stem}).unlink(missing_ok=True)
    for name in (PAGES_DIR, PAGE_PNG_DIR, *REGION_DIRS):
        (batch_dir / name).mkdir()


def convert(document: pymupdf.Document, log_file: Path) -> list[dict]:
    sys.stdout.flush()
    saved = os.dup(1)
    with open(log_file, "w", encoding="utf-8") as log:
        os.dup2(log.fileno(), 1)
        try:
            with contextlib.redirect_stdout(log):
                ocr_function = importlib.import_module(OCR_MODULE).exec_ocr
                chunks = pymupdf4llm.to_markdown(document, page_chunks=True, ocr_function=ocr_function)
        finally:
            sys.stdout.flush()
            os.dup2(saved, 1)
            os.close(saved)
    if len(chunks) != document.page_count:
        raise WorkflowError("converter_page_count", f"converter returned {len(chunks)} pages for {document.page_count}")
    return chunks


def read_ocr_pages(log_file: Path) -> set[int]:
    text = log_file.read_text(encoding="utf-8", errors="replace")
    return {int(index) + 1 for index in OCR_PAGE_LINE.findall(text)}


def build_page(number: int, chunk: dict, page: pymupdf.Page, ocr: bool) -> dict:
    result = {
        "number": number, "ocr": ocr, "tables": [], "figures": [], "formulas": [], "headings": [], "dropped": [], "paragraph_starts": 0,
    }
    boxes = [{**box, "span": chunk["text"][box["pos"][0]:box["pos"][1]].strip()} for box in chunk["page_boxes"]]
    require_known_classes(number, boxes)
    if not ocr:
        boxes = split_rotated_tables(page, boxes)
    formulas = formula_regions(number, boxes)
    parts = []
    for index, box in enumerate(boxes):
        if index in formulas:
            part = formula_part(number, formulas[index], result)
        else:
            part = box_part(number, box, box["span"], page, result)
        if part:
            parts.append(part)
    result["text"] = NEW_PARAGRAPH.join(parts) + "\n" if parts else ""
    return result


def require_known_classes(number: int, boxes: list[dict]) -> None:
    for box in boxes:
        if box["class"] not in KNOWN_CLASSES:
            raise WorkflowError("unknown_box_class", f"page {number}: box class {box['class']!r} was never observed")


def split_rotated_tables(page: pymupdf.Page, boxes: list[dict]) -> list[dict]:
    blocks = page.get_text("dict", flags=ROW_FLAGS)["blocks"]
    result = list(boxes)
    for box in boxes:
        inside = lines_inside(blocks, box["bbox"])
        rotated = [line for line in inside if not horizontal(line)]
        if box["class"] != CLASS_TABLE or len(rotated) * 2 <= len(inside):
            continue
        table = {**box, "bbox": list(union_of(rotated)), "span": "\n".join(line_text(line) for line in rotated)}
        position = next(index for index, entry in enumerate(result) if entry is box)
        result[position] = table
        for orphan in orphan_blocks(blocks, box["bbox"], table["bbox"], result):
            result.insert(insert_position(result, position, orphan), orphan)
    return result


def lines_inside(blocks: list[dict], bbox: list[float]) -> list[dict]:
    rect = pymupdf.Rect(bbox)
    return [line for block in blocks for line in block.get("lines", []) if rect.contains(line_center(line["bbox"]))]


def horizontal(line: dict) -> bool:
    return abs(line["dir"][0] - 1) < DIRECTION_TOLERANCE


def union_of(lines: list[dict]) -> pymupdf.Rect:
    rect = pymupdf.Rect(lines[0]["bbox"])
    for line in lines[1:]:
        rect.include_rect(line["bbox"])
    return rect


def line_text(line: dict) -> str:
    return "".join(span["text"] for span in line["spans"])


def orphan_blocks(blocks: list[dict], old_bbox: list[float], table_bbox: list[float], boxes: list[dict]) -> list[dict]:
    old, table = pymupdf.Rect(old_bbox), pymupdf.Rect(table_bbox)
    others = [pymupdf.Rect(box["bbox"]) for box in boxes if box["class"] != CLASS_TABLE]
    orphans = []
    for block in blocks:
        lines = [line for line in block.get("lines", []) if horizontal(line)]
        centers = [line_center(line["bbox"]) for line in lines]
        if lines and all(old.contains(c) and not table.contains(c) and not any(o.contains(c) for o in others) for c in centers):
            orphans.append({"class": CLASS_TEXT, "bbox": list(union_of(lines)), "span": block_text(lines)})
    return sorted(orphans, key=lambda orphan: orphan["bbox"][1])


def block_text(lines: list[dict]) -> str:
    text = ""
    for line in lines:
        part = line_text(line).strip()
        if text.endswith("-") and HYPHENATED_END.search(text):
            text = text[:-1] + part
        else:
            text = f"{text} {part}" if text else part
    return text


def insert_position(boxes: list[dict], table_index: int, orphan: dict) -> int:
    x0, y0, x1, _ = orphan["bbox"]
    for index in range(table_index + 1, len(boxes)):
        bbox = boxes[index]["bbox"]
        if bbox[0] < x1 and x0 < bbox[2] and bbox[1] > y0:
            return index
    return len(boxes)


def formula_regions(number: int, boxes: list[dict]) -> dict[int, dict | None]:
    regions: dict[int, dict | None] = {}
    for index, box in enumerate(boxes):
        if is_formula(box):
            regions[index] = {"bbox": list(box["bbox"]), "spans": [box["span"]]}
    for index, box in enumerate(boxes):
        if EQUATION_NUMBER.fullmatch(unwrapped(box["span"])):
            partner = row_partner(number, boxes, index)
            region = regions.setdefault(partner, {"bbox": list(boxes[partner]["bbox"]), "spans": [boxes[partner]["span"]]})
            region["bbox"] = union(region["bbox"], box["bbox"])
            region["spans"].append(box["span"])
            regions[index] = None
    return regions


def is_formula(box: dict) -> bool:
    if box["class"] == CLASS_FORMULA:
        content = unwrapped(box["span"])
        return not (BARE_PAGE_NUMBER.fullmatch(content) or EQUATION_NUMBER.fullmatch(content))
    return box["class"] == CLASS_HEADING and FORMULA_HEADING_SIGN in box["span"]


def unwrapped(span: str) -> str:
    return PICTURE_TEXT_MARKUP.sub("", span).strip()


def row_partner(number: int, boxes: list[dict], index: int) -> int:
    x0, y0, _, y1 = boxes[index]["bbox"]
    middle = (y0 + y1) / 2
    left = [
        other for other, box in enumerate(boxes)
        if other != index and box["bbox"][1] <= middle <= box["bbox"][3] and box["bbox"][2] <= x0 + LEFT_TOLERANCE_PT
    ]
    if not left:
        raise WorkflowError("equation_number_alone", f"page {number}: equation number {boxes[index]['span']!r} has no box to its left")
    partner = max(left, key=lambda other: boxes[other]["bbox"][2])
    if boxes[partner]["class"] not in NUMBERED_FORMULA_CLASSES:
        raise WorkflowError(
            "equation_number_alone",
            f"page {number}: equation number {boxes[index]['span']!r} stands next to a {boxes[partner]['class']!r} box",
        )
    return partner


def union(first: list[float], second: list[float]) -> list[float]:
    return [min(first[0], second[0]), min(first[1], second[1]), max(first[2], second[2]), max(first[3], second[3])]


def formula_part(number: int, region: dict | None, result: dict) -> str:
    if region is None:
        return ""
    return add_region(result, "formulas", KIND_FORMULA, number, region["bbox"], " ".join(region["spans"]))


def box_part(number: int, box: dict, span: str, page: pymupdf.Page, result: dict) -> str:
    kind = box["class"]
    if kind in RUNNING_CLASSES and not kept_running_box(number, span):
        result["dropped"].append((list(box["bbox"]), span))
        return ""
    if kind == CLASS_TABLE:
        return add_region(result, "tables", KIND_TABLE, number, box["bbox"], span)
    if kind == CLASS_PICTURE:
        return add_region(result, "figures", KIND_FIGURE, number, box["bbox"], span)
    if not span:
        return ""
    if kind in HEADING_CLASSES:
        heading_id = f"h{number}_{len(result['headings'])}"
        result["headings"].append({"id": heading_id, "page": number, "text": span})
        return placeholder(KIND_HEADING, heading_id)
    if kind == CLASS_TEXT and not result["ocr"]:
        return split_at_paragraph_starts(number, span, text_rows(page, box["bbox"]), result)
    return span


def kept_running_box(number: int, span: str) -> bool:
    return number == 1 and bool(span) and not BARE_PAGE_NUMBER.fullmatch(span)


def add_region(result: dict, key: str, kind: str, number: int, bbox: list[float], span: str) -> str:
    region_id = f"p{number}_{len(result[key])}"
    result[key].append({"id": region_id, "bbox": list(bbox), "current": span})
    return placeholder(kind, region_id)


def text_rows(page: pymupdf.Page, bbox: list[float]) -> list[tuple[float, str]]:
    rect = pymupdf.Rect(bbox)
    lines = [
        line for block in page.get_text("dict", clip=rect, flags=ROW_FLAGS)["blocks"] for line in block.get("lines", [])
        if rect.contains(line_center(line["bbox"]))
    ]
    rows: list[list] = []
    for line in sorted(lines, key=lambda item: (item["bbox"][3], item["bbox"][0])):
        text = "".join(span["text"] for span in line["spans"])
        if rows and abs(line["bbox"][3] - rows[-1][0]) <= ROW_TOLERANCE_PT:
            rows[-1][1].append((line["bbox"][0], text))
        else:
            rows.append([line["bbox"][3], [(line["bbox"][0], text)]])
    return merge_delimiter_rows([(min(x for x, _ in parts), " ".join(text for _, text in sorted(parts))) for _, parts in rows])


def merge_delimiter_rows(rows: list[tuple[float, str]]) -> list[tuple[float, str]]:
    merged, pending = [], []
    for row in rows:
        pending.append(row)
        if WORD_CHAR.search(row[1]):
            merged.append((min(x for x, _ in pending), " ".join(text for _, text in pending)))
            pending = []
    return merged + pending


def line_center(bbox: tuple[float, float, float, float]) -> pymupdf.Point:
    return pymupdf.Point((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def split_at_paragraph_starts(number: int, span: str, rows: list[tuple[float, str]], result: dict) -> str:
    parts, position = [], 0
    for row_text in paragraph_starts(rows):
        found = locate_row(span, row_text, position)
        if found is None:
            raise WorkflowError("paragraph_start_not_found", f"page {number}: indented line {row_text!r} not found in the converter text")
        parts.append(span[position:found].rstrip())
        position = found
    parts.append(span[position:])
    result["paragraph_starts"] += len(parts) - 1
    return NEW_PARAGRAPH.join(part for part in parts if part)


def paragraph_starts(rows: list[tuple[float, str]]) -> list[str]:
    if not rows:
        return []
    left = min(x for x, _ in rows)
    indented = [INDENT_MIN_PT <= x - left <= INDENT_MAX_PT for x, _ in rows]
    at_left = [x - left <= LEFT_TOLERANCE_PT for x, _ in rows]
    if at_left[0] and sum(indented) >= sum(at_left):
        starts = [index for index in range(1, len(rows)) if at_left[index] and indented[index - 1]]
    else:
        starts = [index for index in range(1, len(rows) - 1) if indented[index] and at_left[index + 1]]
    return [rows[index][1] for index in starts if rows[index][1].split()]


def locate_row(span: str, row_text: str, start: int) -> int | None:
    words = row_text.split()[:NEEDLE_WORDS]
    pattern = re.compile(r"(?<!\S)" + MARKUP + (MARKUP + r"\s+" + MARKUP).join(re.escape(word) for word in words))
    match = pattern.search(span, start + 1)
    return match.start() if match else None


def unrotated_original(pdf: Path) -> pymupdf.Document:
    original = pymupdf.open(pdf)
    for page in original:
        page.remove_rotation()
    return original


def write_pages(batch_dir: Path, document: pymupdf.Document, pages: list[dict]) -> None:
    for page in pages:
        (batch_dir / page_md(page["number"])).write_text(page["text"], encoding="utf-8")
        source = document[page["number"] - 1]
        source.get_pixmap(dpi=PAGE_DPI).save(batch_dir / page_png(page["number"]))
        for kind, key in REGION_KINDS:
            for region in page[key]:
                source.get_pixmap(dpi=REGION_DPI, clip=pymupdf.Rect(region["bbox"])).save(batch_dir / region_png(kind, region["id"]))
                current = region["current"] + "\n" if region["current"] else ""
                (batch_dir / region_current(kind, region["id"])).write_text(current, encoding="utf-8")


def bookmarks(document: pymupdf.Document) -> list[dict]:
    return [{"level": level, "title": title, "page": page} for level, title, page in document.get_toc(simple=True)]


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def build_manifest(run: dict, pdf: Path, pages: list[dict]) -> dict:
    return {
        "run_id": run["run_id"],
        "ts_start": run["ts_start"],
        "pdf": str(pdf),
        "pdf_sha256": run["pdf_sha256"],
        "stem": pdf.stem,
        "pages": len(pages),
        "worker_model": run["config"]["worker_model"],
        "tables": [region["id"] for page in pages for region in page["tables"]],
        "figures": [region["id"] for page in pages for region in page["figures"]],
        "formulas": [region["id"] for page in pages for region in page["formulas"]],
        "headings": [heading["id"] for page in pages for heading in page["headings"]],
        "workers": [],
    }


def write_worker_prompts(pdf: Path, batch_dir: Path, manifest: dict) -> list[dict]:
    workers = []
    if manifest["tables"]:
        workers.append(region_worker(pdf, batch_dir, WORKER_TABLES, KIND_TABLE, manifest["tables"]))
    if manifest["figures"]:
        workers.append(region_worker(pdf, batch_dir, WORKER_FIGURES, KIND_FIGURE, manifest["figures"]))
    if manifest["formulas"]:
        workers.append(region_worker(pdf, batch_dir, WORKER_FORMULAS, KIND_FORMULA, manifest["formulas"]))
    workers.append(outline_worker(pdf, batch_dir, manifest["pages"]))
    workers += [page_worker(pdf, batch_dir, first, last) for first, last in page_ranges(manifest["pages"])]
    return workers


def region_worker(pdf: Path, batch_dir: Path, name: str, kind: str, ids: list[str]) -> dict:
    entry = {"name": name, "prompt": f"prompt_{name}.md", "outputs": [region_fixed(kind, region_id) for region_id in ids]}
    values = {"PDF": str(pdf), "DIR": str(batch_dir / region_dir(kind)), "IDS": " ".join(ids)}
    write_prompt(batch_dir, entry, f"{name}_prompt.md", values)
    return entry


def outline_worker(pdf: Path, batch_dir: Path, pages: int) -> dict:
    entry = {"name": WORKER_OUTLINE, "prompt": f"prompt_{WORKER_OUTLINE}.md", "outputs": [HEADINGS_FIXED_FILE]}
    values = {
        "PDF": str(pdf),
        "PAGES": str(pages),
        "OUTPUT": str(batch_dir / HEADINGS_FIXED_FILE),
        "HEADINGS": str(batch_dir / HEADINGS_FILE),
        "BOOKMARKS": str(batch_dir / BOOKMARKS_FILE),
        "PAGE_FILES": f"{batch_dir / PAGES_DIR}/p1.md to p{pages}.md",
    }
    write_prompt(batch_dir, entry, "outline_prompt.md", values)
    return entry


def page_ranges(pages: int) -> list[tuple[int, int]]:
    return [(first, min(first + PAGE_WORKER_PAGES - 1, pages)) for first in range(1, pages + 1, PAGE_WORKER_PAGES)]


def page_worker(pdf: Path, batch_dir: Path, first: int, last: int) -> dict:
    span = f"{first}-{last}"
    entry = {
        "name": f"pages-{span}",
        "prompt": f"prompt_pages_{span}.md",
        "pages": [first, last],
        "outputs": [fixed_page_md(number) for number in range(first, last + 1)],
    }
    values = {
        "PDF": str(pdf),
        "FROM": str(first),
        "TO": str(last),
        "PNG_PATTERN": str(batch_dir / page_png("N")),
        "MD_PATTERN": str(batch_dir / outlined_md("N")),
        "FIXED_PATTERN": str(batch_dir / fixed_page_md("N")),
    }
    write_prompt(batch_dir, entry, "pages_prompt.md", values)
    return entry


def write_prompt(batch_dir: Path, entry: dict, template: str, values: dict[str, str]) -> None:
    text = require_filled(substitute(read_template(template), values))
    (batch_dir / entry["prompt"]).write_text(text, encoding="utf-8")


def format_summary(manifest: dict, batch_dir: Path, pages: list[dict], ocr_pages: set[int]) -> str:
    return "\n".join([
        f"extract ok: {manifest['stem']}",
        f"pages={manifest['pages']} ocr_pages={len(ocr_pages)} tables={len(manifest['tables'])} figures={len(manifest['figures'])} "
        f"formulas={len(manifest['formulas'])} headings={len(manifest['headings'])} paragraph_starts_split={sum(page['paragraph_starts'] for page in pages)}",
        "formulas: " + (" ".join(manifest["formulas"]) or "none"),
        f"batch dir: {batch_dir}",
        f"manifest: {batch_dir / MANIFEST_FILE_NAME}",
        "workers: " + " ".join(worker["name"] for worker in manifest["workers"]),
    ])
