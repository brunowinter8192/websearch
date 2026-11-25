# INFRASTRUCTURE
from pathlib import Path

import pymupdf

from src.pdf.report import Report, WorkflowError

SPREAD_MIN_RATIO = 1.2


# ORCHESTRATOR
def split_spreads_workflow(pdf: str, out: str) -> Report:
    source, target = Path(pdf).resolve(), Path(out).resolve()
    require_paths(source, target)
    with pymupdf.open(source) as document:
        spreads = [page.number for page in document if is_spread(page)]
        if not spreads:
            return Report(f"split-spreads ok: no spread page in {source}, use the PDF as it is\npages={document.page_count} spreads=0", True)
        written = write_split(document, set(spreads), target)
        return Report(format_summary(target, document.page_count, len(spreads), written), True)


# FUNCTIONS
def require_paths(source: Path, target: Path) -> None:
    if not source.is_file():
        raise WorkflowError("pdf_not_found", f"PDF not found: {source}")
    if target == source:
        raise WorkflowError("out_is_source", "--out must differ from --pdf")


# A spread shows two book pages side by side: the page is clearly wider than high
def is_spread(page: pymupdf.Page) -> bool:
    return page.rect.width >= SPREAD_MIN_RATIO * page.rect.height


# Every spread becomes two pages, its left half and its right half; other pages are copied unchanged
def write_split(document: pymupdf.Document, spreads: set[int], target: Path) -> int:
    result = pymupdf.open()
    for number in range(document.page_count):
        if number not in spreads:
            result.insert_pdf(document, from_page=number, to_page=number)
            continue
        for clip in halves(document[number].rect):
            page = result.new_page(width=clip.width, height=clip.height)
            page.show_pdf_page(page.rect, document, number, clip=clip)
    pages = result.page_count
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target, garbage=3, deflate=True)
    result.close()
    return pages


def halves(rect: pymupdf.Rect) -> tuple[pymupdf.Rect, pymupdf.Rect]:
    middle = (rect.x0 + rect.x1) / 2
    return pymupdf.Rect(rect.x0, rect.y0, middle, rect.y1), pymupdf.Rect(middle, rect.y0, rect.x1, rect.y1)


def format_summary(target: Path, pages: int, spreads: int, written: int) -> str:
    return "\n".join([
        f"split-spreads ok: {target}",
        f"pages={pages} spreads={spreads} pages_written={written}",
    ])
