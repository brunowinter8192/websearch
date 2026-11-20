# INFRASTRUCTURE
import json
import struct

import pymupdf
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
    assert "pages=7 ocr_pages=0 tables=0 figures=0 formulas=0 headings=0" in report.text
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


def test_formulas_become_placeholders_crops_and_a_formulas_worker_title_is_a_heading_footnote_is_text(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "First page")], [(LEFT, "Second page")]])
    fake_converter(monkeypatch, [
        chunk(1, [
            ("text", [48, 60, 284, 70], "where the hazard is estimated:"),
            ("formula", [301, 115, 553, 139], "<!-- Start of picture text -->\nkiðtÞ ¼ k0ðtÞ ð1Þ<br><!-- End of picture text -->"),
            ("text", [301, 719, 447, 729], "Peer Pressure ¼ EPj � Concentrationji;"),
            ("formula", [541, 719, 553, 729], "<!-- Start of picture text -->\nð2Þ<br><!-- End of picture text -->"),
            ("text", [32, 663, 284, 724], "left column text"),
        ]),
        chunk(2, [
            ("section-header", [311, 708, 454, 718], "##### Susceptibility ¼ EPj � Concentrationij"),
            ("page-footer", [551, 708, 563, 718], "ð3Þ"),
            ("section-header", [48, 362, 136, 371], "#### 4. Results"),
            ("title", [79, 101, 336, 134], "# **Global Banks as Global Sustainability Regulators?**"),
            ("footnote", [46, 557, 370, 582], "> Address correspondence to John M. Conley."),
        ]),
    ])
    batch_dir = tmp_path / "batch"
    report = extract_workflow(str(pdf), str(batch_dir))
    assert report.ok, report.text
    assert "formulas=3 headings=2" in report.text and "formulas: p1_0 p1_1 p2_0" in report.text
    assert (batch_dir / "pages" / "p1.md").read_text() == (
        "where the hazard is estimated:\n\n<!-- FORMULA p1_0 -->\n\n<!-- FORMULA p1_1 -->\n\nleft column text\n"
    )
    assert (batch_dir / "pages" / "p2.md").read_text() == (
        "<!-- FORMULA p2_0 -->\n\n<!-- HEADING h2_0 -->\n\n<!-- HEADING h2_1 -->\n\n> Address correspondence to John M. Conley.\n"
    )
    assert json.loads((batch_dir / "headings.json").read_text()) == [
        {"id": "h2_0", "page": 2, "text": "#### 4. Results"},
        {"id": "h2_1", "page": 2, "text": "# **Global Banks as Global Sustainability Regulators?**"},
    ]
    assert (batch_dir / "formulas" / "p1_1_current.md").read_text() == (
        "Peer Pressure ¼ EPj � Concentrationji; <!-- Start of picture text -->\nð2Þ<br><!-- End of picture text -->\n"
    )
    assert (batch_dir / "formulas" / "p2_0_current.md").read_text() == "##### Susceptibility ¼ EPj � Concentrationij ð3Þ\n"
    widths = {png_size(batch_dir / "formulas" / f"{name}.png")[0] for name in ("p1_0", "p1_1", "p2_0")}
    assert len(widths) == 1 and widths.pop() > 252 * 200 / 72 - 2
    manifest = read_manifest(batch_dir)
    assert manifest["formulas"] == ["p1_0", "p1_1", "p2_0"]
    workers = {worker["name"]: worker for worker in manifest["workers"]}
    assert list(workers) == ["formulas", "outline", "pages-1-2"]
    assert workers["formulas"]["outputs"] == ["formulas/p1_0_fixed.md", "formulas/p1_1_fixed.md", "formulas/p2_0_fixed.md"]
    formulas_prompt = (batch_dir / "prompt_formulas.md").read_text()
    assert "Formulas: p1_0 p1_1 p2_0" in formulas_prompt and f"Directory: {batch_dir / 'formulas'}" in formulas_prompt
    assert "\\tag{1}" in formulas_prompt and "{{" not in formulas_prompt
    pages_prompt = (batch_dir / "prompt_pages_1-2.md").read_text()
    assert "<!-- FORMULA ... -->" in pages_prompt and "never add or remove one" in pages_prompt


def test_an_equation_number_without_a_box_to_its_left_fails_extract(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "Page")]])
    fake_converter(monkeypatch, [chunk(1, [("text", [48, 60, 284, 70], "Page"), ("page-footer", [551, 708, 563, 718], "ð3Þ")])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert report.text == "extract FAILED (equation_number_alone): page 1: equation number 'ð3Þ' has no box to its left"
    assert read_log(conversion_log)[-1]["failure_class"] == "equation_number_alone"


def test_a_bracket_set_above_its_line_does_not_make_the_line_a_paragraph_start(tmp_path, monkeypatch, conversion_log):
    pdf = tmp_path / "Book.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    lines = ["variables representing direct exposure to certification", "(Di,t), indirect exposure through a corporate group",
             "Gi,g,t), and indirect exposure through a local market", "(Li,t) equal to zero for all points in all years."]
    for index, text in enumerate(lines):
        page.insert_text((LEFT + (5 if index == 2 else 0), 80 + index * 14), text, fontsize=11)
    page.insert_text((LEFT, 80 + 2 * 14 - 8), "(", fontsize=11)
    document.save(pdf)
    span = " ".join(lines[:2]) + " ( " + " ".join(lines[2:])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, span)])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert report.ok, report.text
    assert "paragraph_starts_split=0" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == span + "\n"


def test_references_with_a_hanging_indent_are_split_before_each_reference(tmp_path, monkeypatch, conversion_log):
    rows = [
        (LEFT, "DiMaggio, P. (1991). Introduction. In W. W. Powell & P. J. Dimaggio (Eds.), The new"),
        (LEFT + 12, "institutionalism in organizational analysis (pp. 1-38)."),
        (LEFT, "DiMaggio, P., & Powell, W. (1983). The iron cage revisited: Institutional"),
        (LEFT + 12, "isomorphism and collective rationality in organizational fields. American"),
        (LEFT + 12, "Sociological Review, 48, 147-160."),
    ]
    pdf = write_pdf(tmp_path / "Book.pdf", [rows])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, rows_text(rows))])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert "paragraph_starts_split=1" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == rows_text(rows[:2]) + "\n\n" + rows_text(rows[2:]) + "\n"
