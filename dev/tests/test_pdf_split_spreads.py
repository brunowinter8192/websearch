# INFRASTRUCTURE
import pymupdf
import pytest

from src.pdf.report import WorkflowError
from src.pdf.split_spreads import split_spreads_workflow

PORTRAIT = (400, 600)
SPREAD = (800, 600)


# FUNCTIONS

def write_pdf(path, sizes):
    document = pymupdf.open()
    for width, height in sizes:
        page = document.new_page(width=width, height=height)
        page.insert_text((50, 100), "left")
        page.insert_text((width - 150, 100), "right")
    document.save(path)
    document.close()
    return path


def test_every_spread_becomes_a_left_and_a_right_page_and_other_pages_stay(tmp_path):
    source = write_pdf(tmp_path / "book.pdf", [PORTRAIT, SPREAD, SPREAD])
    target = tmp_path / "out" / "split.pdf"
    report = split_spreads_workflow(str(source), str(target))
    assert report.ok and "pages=3 spreads=2 pages_written=5" in report.text
    with pymupdf.open(target) as document:
        assert [(round(page.rect.width), round(page.rect.height)) for page in document] == [PORTRAIT] * 5
        assert "left" in document[1].get_text(clip=document[1].rect) and "right" in document[2].get_text(clip=document[2].rect)


def test_a_pdf_without_a_spread_is_not_written(tmp_path):
    source = write_pdf(tmp_path / "book.pdf", [PORTRAIT, PORTRAIT])
    target = tmp_path / "split.pdf"
    report = split_spreads_workflow(str(source), str(target))
    assert report.ok and "spreads=0" in report.text and not target.exists()


def test_the_split_pdf_cannot_overwrite_its_source(tmp_path):
    source = write_pdf(tmp_path / "book.pdf", [SPREAD])
    with pytest.raises(WorkflowError) as error:
        split_spreads_workflow(str(source), str(source))
    assert error.value.failure_class == "out_is_source"
