# INFRASTRUCTURE
import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, worker_output, write_pdf, write_pieces
from src.pdf.merge import merge_workflow
from src.pdf.report import WorkflowError
from src.pdf.resplit import resplit_workflow
from src.pdf.sample import sample_workflow
from src.pdf.split import split_workflow


# FUNCTIONS

@pytest.fixture
def split_dir(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    return batch_dir


def marker_positions(book, pages):
    return [book.index(f"<!-- page {page} -->\n") for page in pages]


def test_merge_joins_pieces_of_mixed_sizes_in_page_order(split_dir, conversion_log):
    resplit_workflow(str(split_dir), "1-50")
    resplit_workflow(str(split_dir), "21-40")
    resplit_workflow(str(split_dir), "21-30")
    write_pieces(split_dir)
    report = merge_workflow(str(split_dir))
    assert report.ok
    assert "pieces=6: 1-20 21-25 26-30 31-40 41-50 51-85" in report.text
    book = (split_dir / "Book.md").read_text()
    positions = marker_positions(book, range(1, 86))
    assert positions == sorted(positions)
    assert book.endswith("\n")
    assert [record["record_type"] for record in read_log(conversion_log)] == ["start"]


def test_merge_does_not_split_long_paragraphs(split_dir):
    write_pieces(split_dir)
    long_paragraph = " ".join(f"Zusatz {number} über Äpfel und Größen." for number in range(60))
    (split_dir / "piece_1-50.md").write_text(worker_output(1, 50) + "\n" + long_paragraph + "\n")
    merge_workflow(str(split_dir))
    assert long_paragraph in (split_dir / "Book.md").read_text().split("\n\n")


def test_missing_piece_is_named_logged_and_nothing_is_written(split_dir, conversion_log):
    resplit_workflow(str(split_dir), "51-85")
    write_pieces(split_dir)
    (split_dir / "piece_71-85.md").unlink()
    report = merge_workflow(str(split_dir))
    assert not report.ok
    assert "merge FAILED (missing_piece): 1 of 3 pieces, nothing written" in report.text
    assert "piece 71-85: missing_file piece_71-85.md" in report.text
    assert not (split_dir / "Book.md").exists()
    end = read_log(conversion_log)[-1]
    assert (end["record_type"], end["outcome"], end["failure_class"]) == ("end", "failed", "missing_piece")
    assert end["missing_pieces"] == [{"from": 71, "to": 85}]


def test_merge_after_sampling_started_is_refused(split_dir):
    write_pieces(split_dir)
    merge_workflow(str(split_dir))
    sample_workflow(str(split_dir))
    with pytest.raises(WorkflowError) as raised:
        merge_workflow(str(split_dir))
    assert raised.value.failure_class == "sampling_started"


def test_merge_without_manifest_raises(tmp_path):
    with pytest.raises(WorkflowError) as raised:
        merge_workflow(str(tmp_path))
    assert raised.value.failure_class == "manifest_missing"
