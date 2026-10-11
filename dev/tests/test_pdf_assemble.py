# INFRASTRUCTURE
import json
from collections import Counter
from pathlib import Path

import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, run_extract, worker_output, write_pdf
from src.pdf.assemble import assemble_workflow, check_batch, judged_reference

BLANK_PAGE = 47


# FUNCTIONS

@pytest.fixture
def extracted(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85, blank=(BLANK_PAGE,)))
    batch_dir = tmp_path / "batches"
    run_extract(pdf, batch_dir)
    return batch_dir


def write_batches(batch_dir, ranges, dropped_lines=0):
    for first, last in ranges:
        (batch_dir / f"batch_{first}-{last}.md").write_text(
            worker_output(first, last, dropped_lines, blank=(BLANK_PAGE,)), encoding="utf-8"
        )


def test_assemble_joins_batches_in_page_order(extracted, tmp_path, conversion_log):
    write_batches(extracted, [(51, 85), (1, 50)])
    report = assemble_workflow(str(extracted), str(tmp_path / "out"))
    assert report.ok
    book = (tmp_path / "out" / "Book.md").read_text()
    assert book.index("<!-- page 1 -->") < book.index("<!-- page 51 -->") < book.index("<!-- page 85 -->")
    assert book.endswith("\n")
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["Book.md"]
    start, end = read_log(conversion_log)
    assert end["record_type"] == "end"
    assert end["outcome"] == "ok"
    assert end["failure_class"] is None
    assert end["run_id"] == start["run_id"]
    assert end["md"].endswith("Book.md")
    assert 0.99 < end["char_ratio"] < 1.1


def test_missing_batch_is_named_and_nothing_is_written(extracted, tmp_path, conversion_log):
    write_batches(extracted, [(1, 50)])
    report = assemble_workflow(str(extracted), str(tmp_path / "out"))
    assert not report.ok
    assert "batch 51-85: missing_file" in report.text
    assert not (tmp_path / "out").exists()
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "failed"
    assert end["failure_class"] == "missing_batch"
    assert end["failed_batches"] == [{"from": 51, "to": 85, "reason": "missing_file", "recall": None}]


def test_batch_that_lost_fifteen_percent_of_the_text_fails_the_content_check(extracted, tmp_path, conversion_log):
    write_batches(extracted, [(1, 50)])
    (extracted / "batch_51-85.md").write_text(worker_output(51, 85, dropped_lines=3, blank=(BLANK_PAGE,)))
    report = assemble_workflow(str(extracted), str(tmp_path / "out"))
    assert not report.ok
    assert "batch 51-85: low_recall" in report.text
    assert not (tmp_path / "out").exists()
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "content_check_failed"
    assert end["failure_class"] == "low_recall"
    assert end["failed_batches"][0]["from"] == 51
    assert end["failed_batches"][0]["recall"] < 0.90


def test_batch_that_only_lost_headers_worth_five_percent_passes(extracted, tmp_path):
    write_batches(extracted, [(1, 50), (51, 85)], dropped_lines=1)
    report = assemble_workflow(str(extracted), str(tmp_path / "out"))
    assert report.ok


def test_batch_with_a_missing_page_marker_but_complete_content_passes(extracted, tmp_path):
    write_batches(extracted, [(1, 50), (51, 85)])
    path = extracted / "batch_51-85.md"
    path.write_text(path.read_text().replace("<!-- page 60 -->\n", ""))
    report = assemble_workflow(str(extracted), str(tmp_path / "out"))
    assert report.ok


def test_retry_after_a_failed_assemble_ends_the_same_run_ok(extracted, tmp_path, conversion_log):
    write_batches(extracted, [(1, 50)])
    assert not assemble_workflow(str(extracted), str(tmp_path / "out")).ok
    write_batches(extracted, [(51, 85)])
    assert assemble_workflow(str(extracted), str(tmp_path / "out")).ok
    start, first_end, second_end = read_log(conversion_log)
    assert first_end["run_id"] == second_end["run_id"] == start["run_id"]
    assert (first_end["outcome"], second_end["outcome"]) == ("failed", "ok")


def test_assemble_without_manifest_raises(tmp_path, conversion_log):
    from src.pdf.report import WorkflowError
    with pytest.raises(WorkflowError) as raised:
        assemble_workflow(str(tmp_path), str(tmp_path / "out"))
    assert raised.value.failure_class == "manifest_missing"


@pytest.fixture
def extracted_with_superimposed_page(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85, blank=(BLANK_PAGE,), layered={37: 20}))
    batch_dir = tmp_path / "batches"
    run_extract(pdf, batch_dir)
    return batch_dir


def test_superimposed_text_layer_page_is_named_as_unjudged_and_the_batch_passes(extracted_with_superimposed_page, tmp_path, conversion_log):
    write_batches(extracted_with_superimposed_page, [(1, 50), (51, 85)])
    report = assemble_workflow(str(extracted_with_superimposed_page), str(tmp_path / "out"))
    assert report.ok
    assert "unjudged pages (text layer over 5x the median page of the batch): 37" in report.text
    end = read_log(conversion_log)[-1]
    assert end["outcome"] == "ok"
    assert end["unjudged_pages"] == [37]


def test_superimposed_page_does_not_hide_a_real_loss_in_the_same_batch(extracted_with_superimposed_page, tmp_path, conversion_log):
    write_batches(extracted_with_superimposed_page, [(51, 85)])
    (extracted_with_superimposed_page / "batch_1-50.md").write_text(worker_output(1, 50, dropped_lines=3, blank=(BLANK_PAGE,)))
    report = assemble_workflow(str(extracted_with_superimposed_page), str(tmp_path / "out"))
    assert not report.ok
    assert "batch 1-50: low_recall" in report.text
    assert "unjudged pages" in report.text
    end = read_log(conversion_log)[-1]
    assert end["failure_class"] == "low_recall"
    assert end["unjudged_pages"] == [37]


def test_check_batch_passes_the_superimposed_page_batch_and_names_page_37(extracted_with_superimposed_page):
    manifest = json.loads((extracted_with_superimposed_page / "manifest.json").read_text())
    write_batches(extracted_with_superimposed_page, [(1, 50)])
    result = check_batch(Path(manifest["pdf"]), extracted_with_superimposed_page, manifest["batches"][0])
    assert result.status == "ok"
    assert result.unjudged_pages == (37,)


def pages_of_size(*sizes):
    return {number: Counter({"a": size}) for number, size in enumerate(sizes, start=1)}


def test_outlier_boundary_is_strictly_more_than_five_times_the_median():
    reference, outliers = judged_reference(pages_of_size(100, 100, 100, 500))
    assert outliers == () and sum(reference.values()) == 800
    reference, outliers = judged_reference(pages_of_size(100, 100, 100, 501))
    assert outliers == (4,) and sum(reference.values()) == 300


def test_batch_with_a_zero_median_has_no_outlier_pages():
    reference, outliers = judged_reference(pages_of_size(0, 0, 0, 900))
    assert outliers == () and sum(reference.values()) == 900
