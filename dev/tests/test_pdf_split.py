# INFRASTRUCTURE
import subprocess

import psutil
import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, read_manifest, write_pdf
from src.pdf.report import WorkflowError
from src.pdf.split import split_workflow


# FUNCTIONS

def run_split(pdf, batch_dir):
    return split_workflow(str(pdf), str(batch_dir))


def test_split_writes_fifty_page_pieces_with_prompts_and_manifest(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85, blank=(47,)))
    batch_dir = tmp_path / "batches"
    report = run_split(pdf, batch_dir)
    assert report.ok
    manifest = read_manifest(batch_dir)
    assert [(p["from"], p["to"]) for p in manifest["pieces"]] == [(1, 50), (51, 85)]
    assert [p["output"] for p in manifest["pieces"]] == ["piece_1-50.md", "piece_51-85.md"]
    assert (manifest["stem"], manifest["pages"], manifest["workers"]) == ("Book", 85, 20)
    assert manifest["worker_model"] == "claude-haiku-5-5[1m]"
    assert len(manifest["pdf_sha256"]) == 64
    assert sorted(path.name for path in batch_dir.iterdir()) == ["manifest.json", "prompt_1-50.md", "prompt_51-85.md"]
    assert "prompts: prompt_1-50.md prompt_51-85.md" in report.text


def test_split_reads_only_the_page_count_and_no_page_content(tmp_path, monkeypatch, conversion_log):
    calls = []
    real_run = subprocess.run

    def recording_run(command, *args, **kwargs):
        calls.append(command[0])
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", recording_run)
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(60))
    assert run_split(pdf, tmp_path / "batches").ok
    assert calls == ["pdfinfo"]


def test_split_handles_books_over_one_thousand_pages(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Big.pdf", numbered_pages(1050))
    batch_dir = tmp_path / "batches"
    run_split(pdf, batch_dir)
    pieces = read_manifest(batch_dir)["pieces"]
    assert len(pieces) == 21
    assert (pieces[-1]["from"], pieces[-1]["to"]) == (1001, 1050)


def test_split_takes_no_ram_measurement(tmp_path, monkeypatch, conversion_log):
    def forbidden(*args, **kwargs):
        raise AssertionError("split measured RAM")

    monkeypatch.setattr(psutil, "virtual_memory", forbidden)
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(10))
    assert run_split(pdf, tmp_path / "batches").ok


def test_split_logs_a_start_record_without_text_extraction_fields(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    run_split(pdf, tmp_path / "batches")
    (start,) = read_log(conversion_log)
    assert start["record_type"] == "start"
    assert start["run_id"] == read_manifest(tmp_path / "batches")["run_id"]
    assert (start["pages"], start["attempt"]) == (45, 1)
    assert start["config"]["piece_pages"] == 50
    assert start["config"]["resplit_piece_pages"] == [20, 10, 5, 2, 1]
    assert start["config"]["workers"] == 20
    assert start["config"]["sample_share"] == 0.1
    assert start["config"]["paragraph_limit_bytes"] == 900
    for gone in ("mode", "converter", "converter_version"):
        assert gone not in start
    assert "threshold" not in start["config"]


def test_second_split_of_the_same_pdf_counts_as_attempt_two(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    run_split(pdf, tmp_path / "batches")
    run_split(pdf, tmp_path / "batches")
    first, second = read_log(conversion_log)
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert first["config_hash"] == second["config_hash"]
    assert first["run_id"] != second["run_id"]


def test_split_removes_its_stale_files_and_keeps_foreign_files(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    batch_dir = tmp_path / "batches"
    (batch_dir / "samples" / "run_1").mkdir(parents=True)
    (batch_dir / "samples" / "run_1" / "run.json").write_text("{}")
    (batch_dir / "blocked").mkdir()
    (batch_dir / "blocked" / "piece_1-12.md").write_text("stale")
    for name in ("piece_1-40.md", "part1_1-40.md", "prompt_1-20.md", "Book.md", "outline.md", "notes.txt"):
        (batch_dir / name).write_text("stale")
    run_split(pdf, batch_dir)
    for name in ("piece_1-40.md", "part1_1-40.md", "prompt_1-20.md", "Book.md", "samples", "blocked"):
        assert not (batch_dir / name).exists()
    assert (batch_dir / "outline.md").read_text() == "stale"
    assert (batch_dir / "notes.txt").read_text() == "stale"


def test_missing_pdf_raises_before_any_log_record(tmp_path, conversion_log):
    with pytest.raises(WorkflowError) as raised:
        split_workflow(str(tmp_path / "absent.pdf"), str(tmp_path / "batches"))
    assert raised.value.failure_class == "pdf_not_found"
    assert not conversion_log.exists()
