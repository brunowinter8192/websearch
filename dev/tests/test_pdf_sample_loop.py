# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, write_pdf, write_pieces
from src.pdf.merge import merge_workflow
from src.pdf.publish import publish_workflow
from src.pdf.report import WorkflowError
from src.pdf.sample import sample_workflow
from src.pdf.sample_close import sample_close_workflow
from src.pdf.sample_report import sample_report_workflow
from src.pdf.split import split_workflow

FOOTNOTES = "[^8]: " + " ".join(f"Fußnote acht Satz {number} über Gemeinkosten und Äpfel." for number in range(55))


# FUNCTIONS

@pytest.fixture
def merged(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    write_pieces(batch_dir)
    merge_workflow(str(batch_dir))
    return batch_dir


def open_run(batch_dir):
    sample_workflow(str(batch_dir))
    runs = sorted((batch_dir / "samples").glob("run_*/run.json"))
    return json.loads(runs[-1].read_text()), runs[-1].parent


def worker_finds_nothing(run, run_dir):
    (run_dir / "findings.md").write_text("".join(f"page {page}: no finding\n" for page in run["pages"]))


def worker_adds_footnotes(run, run_dir, excerpt):
    path = run_dir / excerpt["file"]
    path.write_text(path.read_text().rstrip("\n") + "\n\n" + FOOTNOTES + "\n")
    lines = [f"page {page}: {'missing_text: footnote 8 missing' if page == excerpt['pages'][-1] else 'no finding'}\n" for page in run["pages"]]
    (run_dir / "findings.md").write_text("".join(lines))


def test_report_shows_pages_findings_and_every_correction_before_and_after(merged):
    run, run_dir = open_run(merged)
    excerpt = run["excerpts"][0]
    worker_adds_footnotes(run, run_dir, excerpt)
    report = sample_report_workflow(str(merged))
    assert report.ok
    assert f"corrected excerpts: 1 (pages {' '.join(str(page) for page in excerpt['pages'])})" in report.text
    text = (run_dir / "report.md").read_text()
    assert "Pages sampled: " + " ".join(str(page) for page in run["pages"]) in text
    assert f"page {excerpt['pages'][-1]}: missing_text: footnote 8 missing" in text
    assert f"### Pages {' '.join(str(page) for page in excerpt['pages'])} ({excerpt['file']})" in text
    after = text[text.index("after:"):]
    assert FOOTNOTES in after
    assert FOOTNOTES not in text[:text.index("after:")]
    assert (merged / "Book.md").read_text().count(FOOTNOTES) == 0


def test_close_writes_the_correction_into_the_book_and_the_loop_continues(merged):
    before = (merged / "Book.md").read_text()
    run, run_dir = open_run(merged)
    excerpt = run["excerpts"][0]
    worker_adds_footnotes(run, run_dir, excerpt)
    report = sample_close_workflow(str(merged), [])
    assert report.ok
    assert "corrections applied 1, rejected 0" in report.text
    assert "loop continues: open the next run with pdf sample" in report.text
    book = (merged / "Book.md").read_text()
    assert book.count(FOOTNOTES) == 1
    assert book.replace("\n\n" + FOOTNOTES, "") == before
    closed = json.loads((run_dir / "run.json").read_text())
    assert closed["status"] == "closed" and closed["applied"] == [excerpt["file"]]


def test_a_run_without_finding_ends_the_loop_and_no_further_run_opens(merged):
    run, run_dir = open_run(merged)
    worker_adds_footnotes(run, run_dir, run["excerpts"][0])
    sample_close_workflow(str(merged), [])
    second, second_dir = open_run(merged)
    assert not set(run["pages"]) & set(second["pages"])
    worker_finds_nothing(second, second_dir)
    report = sample_close_workflow(str(merged), [])
    assert "loop ended: run 2 applied no correction" in report.text
    assert "pages sampled: 18 of 85" in report.text
    with pytest.raises(WorkflowError) as raised:
        sample_workflow(str(merged))
    assert raised.value.failure_class == "loop_ended"


def test_a_rejected_correction_is_not_applied_and_does_not_continue_the_loop(merged):
    before = (merged / "Book.md").read_text()
    run, run_dir = open_run(merged)
    excerpt = run["excerpts"][0]
    worker_adds_footnotes(run, run_dir, excerpt)
    report = sample_close_workflow(str(merged), [excerpt["pages"][0]])
    assert "corrections applied 0, rejected 1" in report.text
    assert f"rejected: {excerpt['file']}" in report.text
    assert "loop ended: run 1 applied no correction" in report.text
    assert (merged / "Book.md").read_text() == before


def test_rejecting_a_page_that_was_not_sampled_is_refused(merged):
    run, run_dir = open_run(merged)
    worker_finds_nothing(run, run_dir)
    unsampled = next(page for page in range(1, 86) if page not in run["pages"])
    with pytest.raises(WorkflowError) as raised:
        sample_close_workflow(str(merged), [unsampled])
    assert raised.value.failure_class == "reject_unknown_page"


def test_the_loop_ends_when_every_page_was_sampled_even_after_a_correction(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Short.pdf", numbered_pages(3))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    write_pieces(batch_dir)
    merge_workflow(str(batch_dir))
    for number in (1, 2, 3):
        run, run_dir = open_run(batch_dir)
        worker_adds_footnotes(run, run_dir, run["excerpts"][0])
        report = sample_close_workflow(str(batch_dir), [])
    assert "loop ended: every page has been sampled" in report.text
    assert "pages sampled: 3 of 3" in report.text


def test_publish_is_refused_until_the_loop_has_ended(merged, tmp_path):
    out_dir = tmp_path / "out"
    for expected in ("sampling_missing", "run_open", "loop_not_ended"):
        with pytest.raises(WorkflowError) as raised:
            publish_workflow(str(merged), str(out_dir))
        assert raised.value.failure_class == expected
        if expected == "sampling_missing":
            run, run_dir = open_run(merged)
            worker_adds_footnotes(run, run_dir, run["excerpts"][0])
        elif expected == "run_open":
            sample_close_workflow(str(merged), [])
    assert not out_dir.exists()


def test_publish_splits_a_long_correction_to_the_paragraph_limit_and_logs_the_runs(merged, tmp_path, conversion_log):
    run, run_dir = open_run(merged)
    worker_adds_footnotes(run, run_dir, run["excerpts"][0])
    sample_close_workflow(str(merged), [])
    second, second_dir = open_run(merged)
    worker_finds_nothing(second, second_dir)
    sample_close_workflow(str(merged), [])
    assert len(FOOTNOTES.encode("utf-8")) > 2800
    report = publish_workflow(str(merged), str(tmp_path / "out"))
    assert report.ok
    assert "sample runs: 2, pages sampled: 18 of 85, corrections applied: 1" in report.text
    book = (tmp_path / "out" / "Book.md").read_text()
    assert [path.name for path in (tmp_path / "out").iterdir()] == ["Book.md"]
    assert max(len(paragraph.encode("utf-8")) for paragraph in book.split("\n\n")) <= 900
    assert FOOTNOTES.replace(" ", "") in book.replace(" ", "").replace("\n", "")
    assert book.endswith("\n") and not book.endswith("\n\n")
    end = read_log(conversion_log)[-1]
    assert (end["record_type"], end["outcome"], end["failure_class"]) == ("end", "ok", None)
    assert end["md"].endswith("out/Book.md")
    assert end["pieces"] == [[1, 50], [51, 85]]
    assert [entry["run"] for entry in end["sample_runs"]] == [1, 2]
    assert end["sample_runs"][1]["applied"] == []
    assert end["paragraphs_split"] >= 1 and end["paragraphs_over_limit"] == 0
