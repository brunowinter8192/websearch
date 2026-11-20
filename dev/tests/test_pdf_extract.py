# INFRASTRUCTURE
import json
import struct

import pytest

from dev.tests._pdf_fakes import (
    LEFT, conversion_log, prose_rows, read_log, read_manifest, rows_text, write_pdf,
)
from src.pdf import extract
from src.pdf.extract import extract_workflow
from src.pdf.report import WorkflowError

BOX = [LEFT - 2, 60, 560, 400]


# FUNCTIONS

def png_size(path):
    return struct.unpack(">II", path.read_bytes()[16:24])


def chunk(number, boxes):
    text, page_boxes = "", []
    for kind, bbox, span in boxes:
        start = len(text)
        text += span + "\n\n"
        page_boxes.append({"class": kind, "bbox": bbox, "pos": (start, len(text))})
    return {"text": text, "page_boxes": page_boxes, "metadata": {"page_number": number}}


def fake_converter(monkeypatch, chunks, printed=""):
    def to_markdown(document, page_chunks, ocr_function):
        print(printed, flush=True)
        return chunks
    monkeypatch.setattr(extract.pymupdf4llm, "to_markdown", to_markdown)


def glued_page():
    continued = [(LEFT, f"risk of line {number} ends the paragraph from the page before") for number in range(3)]
    return continued, prose_rows("The history of the EP", 4, indented=True)


def test_extract_on_a_generated_pdf_writes_pages_prompts_manifest_and_start_record(tmp_path, conversion_log, capfd):
    pages = [[(LEFT, f"Page {number} line {line} carries ordinary words of text here.") for line in range(6)] for number in range(1, 8)]
    pdf = write_pdf(tmp_path / "Book.pdf", pages, toc=[[1, "Chapter One", 1], [2, "Section", 3]])
    batch_dir = tmp_path / "batch"
    report = extract_workflow(str(pdf), str(batch_dir))
    assert report.ok, report.text
    assert "pages=7 ocr_pages=0 tables=0 figures=0 headings=0" in report.text
    assert "workers: outline pages-1-5 pages-6-7" in report.text
    manifest = read_manifest(batch_dir)
    assert [worker["name"] for worker in manifest["workers"]] == ["outline", "pages-1-5", "pages-6-7"]
    assert manifest["workers"][2]["outputs"] == ["pages/p6_fixed.md", "pages/p7_fixed.md"]
    assert manifest["workers"][0]["outputs"] == ["headings_fixed.json"]
    assert (manifest["stem"], manifest["pages"], len(manifest["pdf_sha256"])) == ("Book", 7, 64)
    assert "Page 3 line 0 carries ordinary words" in (batch_dir / "pages" / "p3.md").read_text()
    assert png_size(batch_dir / "page_png" / "p7.png") == (1240, 1755)
    assert json.loads((batch_dir / "bookmarks.json").read_text()) == [
        {"level": 1, "title": "Chapter One", "page": 1}, {"level": 2, "title": "Section", "page": 3},
    ]
    assert json.loads((batch_dir / "headings.json").read_text()) == []
    prompt = (batch_dir / "prompt_pages_6-7.md").read_text()
    assert "{{" not in prompt and "pages 6 to 7" in prompt
    assert f"{batch_dir}/page_png/pN.png" in prompt and f"{batch_dir}/pages/pN_outlined.md" in prompt
    assert "Change nothing else" in prompt and "[unreadable]" in prompt and "[^*]" in prompt
    assert "Bookmarks can be incomplete or wrong" in (batch_dir / "prompt_outline.md").read_text()
    (start,) = read_log(conversion_log)
    assert (start["record_type"], start["pages"], start["run_id"]) == ("start", 7, manifest["run_id"])
    assert start["config"]["page_worker_pages"] == 5 and start["config"]["ocr"] == "rapidocr"
    assert (batch_dir / "extract_log.txt").is_file()
    assert capfd.readouterr().out == ""


def test_an_indented_line_inside_a_text_box_starts_a_new_paragraph(tmp_path, monkeypatch, conversion_log):
    continued, new = glued_page()
    pdf = write_pdf(tmp_path / "Book.pdf", [continued + new])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, rows_text(continued) + " " + rows_text(new))])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert "paragraph_starts_split=1" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == rows_text(continued) + "\n\n" + rows_text(new) + "\n"


def test_an_ocr_page_is_not_split_and_the_converter_output_goes_to_the_log(tmp_path, monkeypatch, conversion_log, capfd):
    continued, new = glued_page()
    pdf = write_pdf(tmp_path / "Book.pdf", [continued + new])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, rows_text(continued) + " " + rows_text(new))])], "OCR on page.number=0/1.")
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert "ocr_pages=1" in report.text and "paragraph_starts_split=0" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == rows_text(continued) + " " + rows_text(new) + "\n"
    assert "OCR on page.number=0/1." in (tmp_path / "batch" / "extract_log.txt").read_text()
    assert "OCR on page" not in capfd.readouterr().out


def test_boxes_become_placeholders_crops_headings_and_region_workers(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "First page")], [(LEFT, "Second page")]])
    fake_converter(monkeypatch, [
        chunk(1, [
            ("page-header", [254, 37, 443, 63], "World Development Vol. 35, No. 8, pp. 1307–1328, 2007"),
            ("picture", [48, 37, 74, 67], ""),
            ("section-header", [48, 102, 442, 143], "## Banking on the Equator"),
            ("text", [48, 360, 240, 380], "First page"),
            ("page-footer", [237, 641, 254, 648], "1307"),
        ]),
        chunk(2, [
            ("page-header", [48, 42, 65, 49], "1308"),
            ("page-header", [196, 42, 295, 49], "WORLD DEVELOPMENT"),
            ("caption", [143, 66, 348, 74], "Table 1. Descriptive statistics"),
            ("table", [56, 81, 441, 300], "|a|b|\n|---|---|\n|1|2|"),
            ("formula", [574, 528, 606, 543], "<!-- Start of picture text -->\n[31]<br><!-- End of picture text -->"),
            ("list-item", [48, 351, 240, 386], "- Bagnoli, M. (2003). Selling."),
            ("page-footer", [646, 426, 653, 443], ""),
        ]),
    ])
    batch_dir = tmp_path / "batch"
    assert extract_workflow(str(pdf), str(batch_dir)).ok
    assert (batch_dir / "pages" / "p1.md").read_text() == (
        "World Development Vol. 35, No. 8, pp. 1307–1328, 2007\n\n<!-- FIGURE p1_0 -->\n\n<!-- HEADING h1_0 -->\n\nFirst page\n"
    )
    assert (batch_dir / "pages" / "p2.md").read_text() == (
        "Table 1. Descriptive statistics\n\n<!-- TABLE p2_0 -->\n\n"
        "<!-- Start of picture text -->\n[31]<br><!-- End of picture text -->\n\n- Bagnoli, M. (2003). Selling.\n"
    )
    assert json.loads((batch_dir / "headings.json").read_text()) == [{"id": "h1_0", "page": 1, "text": "## Banking on the Equator"}]
    assert (batch_dir / "tables" / "p2_0_current.md").read_text() == "|a|b|\n|---|---|\n|1|2|\n"
    assert (batch_dir / "figures" / "p1_0_current.md").read_text() == ""
    assert png_size(batch_dir / "tables" / "p2_0.png") == (1070, 609)
    manifest = read_manifest(batch_dir)
    assert (manifest["tables"], manifest["figures"], manifest["headings"]) == (["p2_0"], ["p1_0"], ["h1_0"])
    workers = {worker["name"]: worker for worker in manifest["workers"]}
    assert list(workers) == ["tables", "figures", "outline", "pages-1-2"]
    assert workers["tables"]["outputs"] == ["tables/p2_0_fixed.md"]
    assert workers["figures"]["outputs"] == ["figures/p1_0_fixed.md"]
    tables_prompt = (batch_dir / "prompt_tables.md").read_text()
    assert "Tables: p2_0" in tables_prompt and f"Directory: {batch_dir / 'tables'}" in tables_prompt
    assert "Change nothing else. No italics, no bold, no indents" in tables_prompt
    figures_prompt = (batch_dir / "prompt_figures.md").read_text()
    assert "**Figure description (not source text):**" in figures_prompt
    assert "Do not give a value for every single data point" in figures_prompt


def test_a_box_class_never_observed_fails_extract_and_is_logged(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "Page")]])
    fake_converter(monkeypatch, [chunk(1, [("code", BOX, "print(1)")])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert not report.ok
    assert report.text == "extract FAILED (unknown_box_class): page 1: box class 'code' was never observed"
    assert read_log(conversion_log)[-1]["failure_class"] == "unknown_box_class"


def test_extract_removes_its_stale_files_and_keeps_foreign_files(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "Page")]])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, "Page")])])
    batch_dir = tmp_path / "batch"
    for name in ("samples/run_1", "pages", "tables"):
        (batch_dir / name).mkdir(parents=True)
    for name in ("samples/run_1/run.json", "pages/p9_fixed.md", "tables/p9_0_fixed.md", "prompt_pages_6-10.md",
                 "Book.md", "headings_fixed.json", "notes.txt"):
        (batch_dir / name).write_text("stale")
    assert extract_workflow(str(pdf), str(batch_dir)).ok
    for name in ("samples", "pages/p9_fixed.md", "tables/p9_0_fixed.md", "prompt_pages_6-10.md", "Book.md", "headings_fixed.json"):
        assert not (batch_dir / name).exists()
    assert (batch_dir / "notes.txt").read_text() == "stale"


def test_missing_pdf_raises_before_any_log_record(tmp_path, conversion_log):
    with pytest.raises(WorkflowError) as raised:
        extract_workflow(str(tmp_path / "absent.pdf"), str(tmp_path / "batch"))
    assert raised.value.failure_class == "pdf_not_found"
    assert not conversion_log.exists()
