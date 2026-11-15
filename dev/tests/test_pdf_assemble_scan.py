# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, run_extract, worker_output, write_pdf
from src.pdf.assemble import assemble_workflow

PAGES = 85


# FUNCTIONS

@pytest.fixture
def scan(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Scan.pdf", numbered_pages(PAGES, blank=tuple(range(1, PAGES + 1))))
    batch_dir = tmp_path / "batches"
    run_extract(pdf, batch_dir)
    for first, last in ((1, 50), (51, PAGES)):
        (batch_dir / f"batch_{first}-{last}.md").write_text(worker_output(first, last), encoding="utf-8")
    return batch_dir


def control_pages(batch_dir):
    return json.loads((batch_dir / "manifest.json").read_text())["control_pages"]


def page_entry(page, findings=()):
    return {"page": page, "batch": "batch_1-50.md" if page <= 50 else f"batch_51-{PAGES}.md",
            "correct": not findings, "findings": list(findings)}


def write_control(batch_dir, entries):
    (batch_dir / "control.json").write_text(json.dumps({"pdf": "Scan.pdf", "pages": entries}), encoding="utf-8")


def test_clean_control_writes_the_book_without_counting_characters(scan, tmp_path, conversion_log):
    pages = control_pages(scan)
    write_control(scan, [page_entry(page) for page in pages])
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert report.ok
    assert f"control: {len(pages)} pages checked, 0 grave and 0 minor findings" in report.text
    assert "recall" not in report.text
    book = (tmp_path / "out" / "Scan.md").read_text()
    assert book.index("<!-- page 1 -->") < book.index("<!-- page 85 -->")
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "ok"
    assert end["chars_ref"] == 0 and end["char_ratio"] is None and end["chars_out"] > 0
    assert end["control_pages"] == pages
    assert end["control_checked"] == pages
    assert end["control_grave"] == [] and end["control_minor"] == []


def test_minor_findings_are_named_and_the_book_is_still_written(scan, tmp_path, conversion_log):
    pages = control_pages(scan)
    minor = {"kind": "other", "grave": False, "detail": "heading level 2 instead of 3"}
    write_control(scan, [page_entry(pages[0], [minor])] + [page_entry(page) for page in pages[1:]])
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert report.ok
    assert f"page {pages[0]} minor: other: heading level 2 instead of 3" in report.text
    assert (tmp_path / "out" / "Scan.md").is_file()
    end = read_log(conversion_log)[-1]
    assert end["control_minor"] == [pages[0]] and end["control_grave"] == []


def test_one_grave_finding_writes_nothing_and_names_the_page(scan, tmp_path, conversion_log):
    pages = control_pages(scan)
    grave = {"kind": "misread_number", "grave": True, "detail": "image: 1.234, text: 1.324"}
    write_control(scan, [page_entry(pages[-1], [grave])] + [page_entry(page) for page in pages[:-1]])
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert not report.ok
    assert "assemble FAILED (control_grave)" in report.text
    assert f"page {pages[-1]} grave: misread_number: image: 1.234, text: 1.324" in report.text
    assert not (tmp_path / "out").exists()
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "content_check_failed"
    assert end["failure_class"] == "control_grave"
    assert end["control_grave"] == [pages[-1]]


def test_grave_finding_wins_over_a_correct_flag(scan, tmp_path):
    pages = control_pages(scan)
    entry = page_entry(pages[0], [{"kind": "missing_paragraph", "grave": True, "detail": "last paragraph"}])
    entry["correct"] = True
    write_control(scan, [entry] + [page_entry(page) for page in pages[1:]])
    assert not assemble_workflow(str(scan), str(tmp_path / "out")).ok


def test_missing_control_json_fails_and_names_the_drawn_pages(scan, tmp_path, conversion_log):
    pages = control_pages(scan)
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert not report.ok
    assert "assemble FAILED (control_missing)" in report.text
    assert "control: control.json missing, drawn pages " + " ".join(str(page) for page in pages) in report.text
    assert not (tmp_path / "out").exists()
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "failed" and end["failure_class"] == "control_missing"
    assert end["control_missing"] == pages


def test_drawn_page_missing_in_control_json_fails_and_extra_pages_are_tolerated(scan, tmp_path, conversion_log):
    pages = control_pages(scan)
    extra = next(page for page in range(1, PAGES + 1) if page not in pages)
    write_control(scan, [page_entry(page) for page in pages[1:]] + [page_entry(extra)])
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert not report.ok
    assert "assemble FAILED (control_incomplete)" in report.text
    assert f"control pages missing in control.json: {pages[0]}" in report.text
    end = read_log(conversion_log)[-1]
    assert end["failure_class"] == "control_incomplete"
    assert end["control_missing"] == [pages[0]]
    assert extra in end["control_checked"]


def test_missing_batch_file_fails_as_in_text_mode(scan, tmp_path, conversion_log):
    write_control(scan, [page_entry(page) for page in control_pages(scan)])
    (scan / f"batch_51-{PAGES}.md").unlink()
    report = assemble_workflow(str(scan), str(tmp_path / "out"))
    assert not report.ok
    assert f"batch 51-{PAGES}: missing_file" in report.text
    end = read_log(conversion_log)[-1]
    assert end["failure_class"] == "missing_batch"


def test_retry_after_the_control_worker_delivers_ends_the_same_run_ok(scan, tmp_path, conversion_log):
    assert not assemble_workflow(str(scan), str(tmp_path / "out")).ok
    write_control(scan, [page_entry(page) for page in control_pages(scan)])
    assert assemble_workflow(str(scan), str(tmp_path / "out")).ok
    start, first_end, second_end = read_log(conversion_log)
    assert first_end["run_id"] == second_end["run_id"] == start["run_id"]
    assert (first_end["failure_class"], second_end["outcome"]) == ("control_missing", "ok")
