# INFRASTRUCTURE
from dev.tests._pdf_fakes import conversion_log, numbered_pages, worker_output, write_pdf
from src.pdf.resplit import resplit_workflow
from src.pdf.split import split_workflow
from src.pdf.status import status_workflow


# FUNCTIONS

def test_status_names_complete_incomplete_and_missing_pieces(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    resplit_workflow(str(batch_dir), "51-85")
    (batch_dir / "piece_1-50.md").write_text(worker_output(1, 50))
    (batch_dir / "piece_51-70.md").write_text(worker_output(51, 55) + "\n<!-- page 56 -->\n\nThe difference between the\n")
    report = status_workflow(str(batch_dir))
    assert report.ok
    assert report.text.splitlines() == [
        "pieces complete: 1 of 3",
        "  piece 1-50: complete",
        "  piece 51-70: incomplete (no page marker for pages 57 58 59 60 61 62 63 64 65 66 67 68 69 70)",
        "  piece 71-85: missing",
    ]


def test_a_page_without_content_counts_when_its_marker_is_there(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(3, blank=(2,)))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    (batch_dir / "piece_1-3.md").write_text("<!-- page 1 -->\n\nText.\n\n<!-- page 2 -->\n\n<!-- page 3 -->\n\nText.\n")
    assert "piece 1-3: complete" in status_workflow(str(batch_dir)).text
