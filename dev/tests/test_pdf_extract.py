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
    assert f"{batch_dir}/page_png/pN.png" in prompt and f"{batch_dir}/pages/pN_fixed.md: the extracted Markdown of the page. This is the file you repair, in place." in prompt
    assert "_outlined.md" not in prompt and "Its first line is <!-- REPAIR PENDING -->." in prompt
    assert "only with the Edit tool, one small edit at a time" in prompt and "Never use the Write tool" in prompt
    assert "remove the line <!-- REPAIR PENDING --> with one last Edit" in prompt
    assert "You are not asked to reproduce, retype or rewrite any content" in prompt
    assert "Change nothing else" in prompt and "[unreadable]" in prompt and "[^*]" in prompt
    assert "Bookmarks can be incomplete or wrong" in (batch_dir / "prompt_outline.md").read_text()
    assert "Every entry on it gets level 0, also the title of the work printed there." in (batch_dir / "prompt_outline.md").read_text()
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
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "First page")], [(LEFT, "Table 1. Descriptive statistics")]])
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
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "where the hazard is estimated:")], [(LEFT, "4. Results")]])
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


def test_page_images_and_crops_come_from_the_pdf_as_printed_not_from_the_converted_document(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Scan.pdf", [[(LEFT, "all but economic matters. It is, however")], [(LEFT, "A landscape table page")]])
    rotated = pymupdf.open(pdf)
    rotated[1].set_rotation(90)
    rotated.save(tmp_path / "Book.pdf")
    pdf = tmp_path / "Book.pdf"

    def to_markdown(document, page_chunks, ocr_function):
        for page in document:
            page.remove_rotation()
        document[0].insert_text((LEFT, 82), "OCR TEXT DRAWN OVER THE SCAN", fontsize=11)
        print("OCR on page.number=0/2.", flush=True)
        return [chunk(1, [("table", [LEFT - 2, 60, 400, 100], "|a|")]), chunk(2, [("text", BOX, "A landscape table page")])]
    monkeypatch.setattr(extract.pymupdf4llm, "to_markdown", to_markdown)
    batch_dir = tmp_path / "batch"
    assert extract_workflow(str(pdf), str(batch_dir)).ok
    printed = pymupdf.open(pdf)
    for number in (1, 2):
        expected = printed[number - 1].get_pixmap(dpi=150)
        assert pymupdf.Pixmap(str(batch_dir / "page_png" / f"p{number}.png")).samples == expected.samples
    crop = printed[0].get_pixmap(dpi=200, clip=pymupdf.Rect(LEFT - 2, 60, 400, 100))
    assert pymupdf.Pixmap(str(batch_dir / "tables" / "p1_0.png")).samples == crop.samples


def coverage_pdf(path, second_page_line):
    document = pymupdf.open()
    first = document.new_page(width=595, height=842)
    for (x, y), text in [
        ((LEFT, 80), "Banking on the Equator"), ((LEFT, 120), "the market for project fi-"), ((LEFT, 134), "nance is large today."),
        ((LEFT, 160), "Carlson3,4and Benedict"), ((LEFT, 175), "of deforestation \u02c6Pi,t. We"), ((LEFT, 200), "s=1 Sg"), ((LEFT, 260), "prices and prices"),
    ]:
        first.insert_text((x, y), text, fontsize=11)
    second = document.new_page(width=595, height=842)
    for (x, y), text in [((LEFT, 40), "BANKING ON THE EQUATOR"), ((LEFT, 80), second_page_line), ((LEFT, 300), "BANKING ON THE EQUATOR")]:
        second.insert_text((x, y), text, fontsize=11)
    document.save(path)
    return path


def coverage_chunks():
    return [
        chunk(1, [
            ("text", [60, 60, 560, 100], "**Banking** on the<br>Equator"),
            ("text", [60, 105, 560, 140], "the market for project finance is large today."),
            ("text", [60, 145, 560, 168], "Carlson<sup>3,4</sup> and Benedict"),
            ("text", [60, 168, 560, 180], "of deforestation _P_<sup>\u02c6</sup> _i,t_ . We"),
            ("formula", [60, 185, 200, 205], "<!-- Start of picture text -->\nSs = g 1<br><!-- End of picture text -->"),
            ("table", [60, 245, 560, 265], "|prices and|"),
        ]),
        chunk(2, [
            ("page-header", [60, 25, 560, 45], "BANKING ON THE EQUATOR"),
            ("text", [60, 60, 560, 100], "Second page."),
            ("text", [60, 285, 560, 305], ""),
        ]),
    ]


def test_extract_stops_when_words_of_the_text_layer_are_missing_but_accepts_the_converters_normal_changes(tmp_path, monkeypatch, conversion_log):
    fake_converter(monkeypatch, coverage_chunks())
    covered = coverage_pdf(tmp_path / "Covered.pdf", "Second page.")
    report = extract_workflow(str(covered), str(tmp_path / "covered"))
    assert report.ok, report.text
    lost = coverage_pdf(tmp_path / "Lost.pdf", "Second page text continues here.")
    report = extract_workflow(str(lost), str(tmp_path / "lost"))
    assert report.text == (
        "extract FAILED (text_not_covered): page 2: 3 words of the PDF text layer are missing from the extracted page, "
        "for example: continues text here."
    )
    assert read_log(conversion_log)[-1]["failure_class"] == "text_not_covered"


def test_a_rotated_table_box_spanning_the_other_column_gives_its_text_back_to_the_page(tmp_path, monkeypatch, conversion_log):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    rotated = ["Table 9 Correlation table.", "EPi 1", "EPj 0.057*** 1", "Market Size 0.069***", "Controversial Deals 0.211***",
               "Exposure 0.304***", "p < 0.10, ** p < 0.05"]
    for index, text in enumerate(rotated):
        page.insert_text((90 + index * 15, 700), text, fontsize=9, rotate=90)
    for y, text in [(100, "some light to our findings."), (250, "6.2. Sub-sample analyses"), (330, "When discussing the external pres-"),
                    (344, "sure we argue."), (500, "Table 7 presents the results."), (650, "7. Conclusion")]:
        page.insert_text((320, y), text, fontsize=11)
    document.save(tmp_path / "Book.pdf")
    fake_converter(monkeypatch, [chunk(1, [
        ("text", [310, 88, 560, 104], "some light to our findings."),
        ("table", [50, 50, 560, 800], "|some light|EPi<br>garbled cells|"),
        ("text", [310, 488, 560, 504], "Table 7 presents the results."),
    ])])
    batch_dir = tmp_path / "batch"
    report = extract_workflow(str(tmp_path / "Book.pdf"), str(batch_dir))
    assert report.ok, report.text
    assert (batch_dir / "pages" / "p1.md").read_text().split("\n\n") == [
        "some light to our findings.", "<!-- TABLE p1_0 -->", "6.2. Sub-sample analyses",
        "When discussing the external pressure we argue.", "Table 7 presents the results.", "7. Conclusion\n",
    ]
    assert sorted((batch_dir / "tables" / "p1_0_current.md").read_text().split("\n")[:-1]) == sorted(rotated)
    width, _ = png_size(batch_dir / "tables" / "p1_0.png")
    assert width < (310 - 50) * 200 / 72


def test_words_missing_inside_a_table_are_listed_for_the_table_worker_instead_of_stopping_extract(tmp_path, monkeypatch, conversion_log):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    for y, text in [(80, "Ecological links"), (200, "forest resilience within the RSPO certified areas"), (214, "during droughts")]:
        page.insert_text((LEFT, y), text, fontsize=11)
    document.save(tmp_path / "Book.pdf")
    fake_converter(monkeypatch, [chunk(1, [
        ("text", [60, 60, 560, 100], "Ecological links"),
        ("table", [60, 185, 560, 220], "|forest resilience within the RSPO certified area|"),
    ])])
    batch_dir = tmp_path / "batch"
    report = extract_workflow(str(tmp_path / "Book.pdf"), str(batch_dir))
    assert report.ok, report.text
    assert "region words missing from the converter text: p1_0=3" in report.text
    assert (batch_dir / "tables" / "p1_0_missing.txt").read_text() == "areas\nduring\ndroughts\n"
    prompt = (batch_dir / "prompt_tables.md").read_text()
    assert "Tables with a missing-words file: p1_0" in prompt
    assert "must appear in <id>_fixed.md at the place where the image shows it" in prompt


def test_a_drop_cap_beside_the_first_rows_does_not_make_them_a_paragraph_start(tmp_path, monkeypatch, conversion_log):
    rows = ["n recent years, changing public expectations have increasingly", "induced firms to publicly declare their commitments to",
            "a wide variety of public interest concerns into their corporate", "practices. In the United States and elsewhere, demands for",
            "firms to demonstrate sound management have intensified."]
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((LEFT, 108), "I", fontsize=40)
    for index, text in enumerate(rows):
        page.insert_text((LEFT + (16 if index < 3 else 0), 80 + index * 14), text, fontsize=11)
    document.save(tmp_path / "Book.pdf")
    span = " ".join(rows[:2]) + " I" + " ".join(rows[2:])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, span)])])
    report = extract_workflow(str(tmp_path / "Book.pdf"), str(tmp_path / "batch"))
    assert report.ok, report.text
    assert "paragraph_starts_split=0" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == span + "\n"


def test_a_table_box_reaching_into_the_text_column_gives_the_column_back_to_the_page(tmp_path, monkeypatch, conversion_log):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    for y, text in [(80, "Interviewee"), (100, "11. Manager"), (120, "12. Deputy"), (140, "13. Director")]:
        page.insert_text((50, y), text, fontsize=9)
    for y, x, text in [(70, 312, "Biermann, F., 2007. Earth system governance."), (100, 312, "Bitzer, V., 2008. Intersectoral partnerships"),
                       (110, 322, "for a sustainable coffee"), (120, 322, "chain."), (130, 312, "Cashore, B., 2002. Legitimacy and"),
                       (140, 322, "governance."), (170, 312, "RSPO, 2008. Minutes of the 5th General Assembly.")]:
        page.insert_text((x, y), text, fontsize=8)
    document.save(tmp_path / "Book.pdf")
    fake_converter(monkeypatch, [chunk(1, [
        ("text", [310, 60, 562, 74], "Biermann, F., 2007. Earth system governance."),
        ("table", [48, 72, 562, 160], "|Interviewee|Biermann<br>Bitzer, V., 2008.|\n|---|---|\n|11. Manager|Cashore|"),
        ("text", [310, 162, 562, 174], "RSPO, 2008. Minutes of the 5th General Assembly."),
    ])])
    batch_dir = tmp_path / "batch"
    report = extract_workflow(str(tmp_path / "Book.pdf"), str(batch_dir))
    assert report.ok, report.text
    assert "region words missing from the converter text: none" in report.text
    assert (batch_dir / "pages" / "p1.md").read_text().split("\n\n") == [
        "Biermann, F., 2007. Earth system governance.", "<!-- TABLE p1_0 -->",
        "Bitzer, V., 2008. Intersectoral partnerships for a sustainable coffee chain.", "Cashore, B., 2002. Legitimacy and governance.",
        "RSPO, 2008. Minutes of the 5th General Assembly.\n",
    ]
    assert (batch_dir / "tables" / "p1_0_current.md").read_text() == "Interviewee\n11. Manager\n12. Deputy\n13. Director\n"
    width, _ = png_size(batch_dir / "tables" / "p1_0.png")
    assert width < (310 - 48) * 200 / 72


def test_tiny_hidden_text_of_the_text_layer_is_not_required_in_the_extracted_page(tmp_path, monkeypatch, conversion_log):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((LEFT, 70), "1Original Article BASR", fontsize=2, color=(1, 1, 1))
    page.insert_text((LEFT, 100), "Institutional Pressures and Voluntary Codes", fontsize=11)
    document.save(tmp_path / "Book.pdf")
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, "Institutional Pressures and Voluntary Codes")])])
    report = extract_workflow(str(tmp_path / "Book.pdf"), str(tmp_path / "batch"))
    assert report.ok, report.text


def test_a_note_mark_the_converter_moved_before_its_word_still_covers_the_word(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "on different signals and informational cues.21 As such, the composition")]])
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, "on different signals and informational 21 cues. As such, the composition")])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert report.ok, report.text


SCHELLING_ROWS = [
    (LEFT + 10, "I have often been glad that I wasn't in charge. It is easy enough to"),
    (LEFT, "see plainly that there is too much inequality, and to help reduce it"),
    (LEFT, "more than a sense of direction."),
    (LEFT + 10, "Discomfort also arises when, intent on speeding toward an ever-"),
    (LEFT, "receding goal, the goal suddenly stops receding and we threaten"),
]
SCHELLING_SPAN = (
    "I have **o** ften been glad that I wasn't in charge. It is easy en **o** ugh t **o** see plainly that there is t **oo** much "
    "inequality _,_ and t **o** help reduce it m **o** re than a sense **o** f directi **o** n. Disc **o** mf **o** rt als **o** arises "
    "when _,_ intent **o** n speeding t **o** ward an everreceding g **o** al _,_ the goal suddenly st **op** s receding and we threaten"
)
BAUMOL_ROWS = [
    (LEFT + 14, "That is why a businessperson who really favors effective action"),
    (LEFT + 14, "to cure the environmental damage caused by the industry can con-"),
    (LEFT + 14, "tribute most effectively toward that goal not by attempts to"),
    (LEFT + 14, "institute a voluntary program within her own firm, but by"),
    (LEFT + 14, "supporting well-designed legislation that will impose such behavior."),
]
BAUMOL_SPAN = (
    "That is why a businessperson who really favors effective action to cure the environmental damage caused by the industry can "
    "contribute most effectively toward that goal _not_ by attempts to \\, institute a voluntary program within her own firm, but by "
    "supporting well-designed legislation that will impose such behavior."
)


def scan_with_text_layer(path, rows, speck_row=None):
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    for index, (x, text) in enumerate(rows):
        page.insert_text((x, 80 + index * 14), text, fontsize=11, render_mode=3)
    if speck_row is not None:
        page.insert_text((LEFT, 80 + speck_row * 14), "\\,", fontsize=8, render_mode=3)
    document.save(path)
    return path


@pytest.mark.parametrize("rows, span, speck_row", [(SCHELLING_ROWS, SCHELLING_SPAN, None), (BAUMOL_ROWS, BAUMOL_SPAN, 3)], ids=["schelling", "baumol"])
def test_a_page_whose_text_layer_is_invisible_ocr_over_a_scan_is_not_split(tmp_path, monkeypatch, conversion_log, rows, span, speck_row):
    pdf = scan_with_text_layer(tmp_path / "Book.pdf", rows, speck_row)
    fake_converter(monkeypatch, [chunk(1, [("text", BOX, span)])])
    report = extract_workflow(str(pdf), str(tmp_path / "batch"))
    assert report.ok, report.text
    assert "ocr_pages=0" in report.text and "paragraph_starts_split=0 invisible_text_pages=1" in report.text
    assert (tmp_path / "batch" / "pages" / "p1.md").read_text() == span + "\n"


def test_running_boxes_kept_on_page_one_are_listed_in_the_manifest(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", [[(LEFT, "First page text"), (LEFT, "JCC 18 Summer 2005")], [(LEFT, "Second page text"), (LEFT, "JCC 18 Summer 2005")]])
    fake_converter(monkeypatch, [
        chunk(1, [("text", [60, 60, 560, 85], "First page text"), ("page-footer", [60, 88, 560, 100], "**JCC 18** _Summer 2005_"),
                  ("page-footer", [500, 88, 560, 100], "99")]),
        chunk(2, [("text", [60, 60, 560, 85], "Second page text"), ("page-footer", [60, 88, 560, 100], "**JCC 18** _Summer 2005_")]),
    ])
    batch_dir = tmp_path / "batch"
    assert extract_workflow(str(pdf), str(batch_dir)).ok
    assert read_manifest(batch_dir)["running"] == ["**JCC 18** _Summer 2005_"]
    assert (batch_dir / "pages" / "p1.md").read_text() == "First page text\n\n**JCC 18** _Summer 2005_\n"
