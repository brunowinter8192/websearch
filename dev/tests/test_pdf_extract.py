# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_log, run_extract, write_pdf
from src.pdf.extract import extract_workflow
from src.pdf.report import WorkflowError


# FUNCTIONS

def test_extract_writes_anchors_prompts_and_manifest_for_forty_page_batches(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85, blank=(47,)))
    batch_dir = tmp_path / "batches"
    report = run_extract(pdf, batch_dir, monkeypatch, available_gb=20.0)
    assert report.ok
    manifest = json.loads((batch_dir / "manifest.json").read_text())
    assert [(b["from"], b["to"]) for b in manifest["batches"]] == [(1, 40), (41, 80), (81, 85)]
    assert manifest["stem"] == "Book"
    assert manifest["pages"] == 85
    assert manifest["workers"] == 3
    assert manifest["worker_model"] == "claude-haiku-5-5[1m]"
    for batch in manifest["batches"]:
        assert (batch_dir / batch["anchor"]).is_file()
        assert (batch_dir / batch["prompt"]).is_file()
    anchor = (batch_dir / "anchor_41-80.md").read_text()
    assert "<!-- page 41 -->" in anchor and "<!-- page 47 -->" in anchor and "<!-- page 80 -->" in anchor
    assert "Kapitel 41 Zeile 1" in anchor
    assert "Kapitel 81" not in anchor


def test_extract_limits_workers_by_injected_free_ram(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85))
    run_extract(pdf, tmp_path / "batches", monkeypatch, available_gb=10.0)
    assert json.loads((tmp_path / "batches" / "manifest.json").read_text())["workers"] == 2


def test_extract_handles_books_over_one_thousand_pages(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Big.pdf", numbered_pages(1050))
    batch_dir = tmp_path / "batches"
    report = run_extract(pdf, batch_dir, monkeypatch)
    assert report.ok
    manifest = json.loads((batch_dir / "manifest.json").read_text())
    assert len(manifest["batches"]) == 27
    assert "<!-- page 1050 -->" in (batch_dir / "anchor_1041-1050.md").read_text()
    assert "Kapitel 1050 Zeile 1" in (batch_dir / "anchor_1041-1050.md").read_text()


def test_extract_logs_a_start_record_before_any_end_record(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    run_extract(pdf, tmp_path / "batches", monkeypatch)
    (start,) = read_log(conversion_log)
    manifest = json.loads((tmp_path / "batches" / "manifest.json").read_text())
    assert start["record_type"] == "start"
    assert start["run_id"] == manifest["run_id"]
    assert start["pages"] == 45
    assert start["converter"] == "liteparse"
    assert start["attempt"] == 1
    assert start["config"]["batch_pages"] == 40
    assert start["config"]["worker_model"] == "claude-haiku-5-5[1m]"
    assert len(start["pdf_sha256"]) == 64


def test_second_extract_of_the_same_pdf_counts_as_attempt_two(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    run_extract(pdf, tmp_path / "batches", monkeypatch)
    run_extract(pdf, tmp_path / "batches", monkeypatch)
    first, second = read_log(conversion_log)
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert first["config_hash"] == second["config_hash"]
    assert first["run_id"] != second["run_id"]


def test_extract_removes_stale_batch_files_but_keeps_foreign_files(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(45))
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    for name in ("batch_1-40.md", "batch_41-80.md", "part1_1-40.md", "anchor_1-20.md", "prompt_1-20.md", "notes.txt"):
        (batch_dir / name).write_text("stale")
    run_extract(pdf, batch_dir, monkeypatch)
    assert not (batch_dir / "batch_1-40.md").exists()
    assert not (batch_dir / "batch_41-80.md").exists()
    assert not (batch_dir / "part1_1-40.md").exists()
    assert not (batch_dir / "anchor_1-20.md").exists()
    assert not (batch_dir / "prompt_1-20.md").exists()
    assert (batch_dir / "notes.txt").read_text() == "stale"


def test_pdf_without_text_layer_stops_with_an_error_and_an_end_record(tmp_path, monkeypatch, conversion_log):
    pdf = write_pdf(tmp_path / "Scan.pdf", numbered_pages(5, blank=(1, 2, 3, 4, 5)))
    batch_dir = tmp_path / "batches"
    report = run_extract(pdf, batch_dir, monkeypatch)
    assert not report.ok
    assert "no_text_layer" in report.text
    assert not (batch_dir / "manifest.json").exists()
    start, end = read_log(conversion_log)
    assert start["record_type"] == "start"
    assert end["record_type"] == "end"
    assert end["run_id"] == start["run_id"]
    assert end["outcome"] == "failed"
    assert end["failure_class"] == "no_text_layer"


def test_missing_pdf_raises_before_any_log_record(tmp_path, conversion_log):
    with pytest.raises(WorkflowError) as raised:
        extract_workflow(str(tmp_path / "absent.pdf"), str(tmp_path / "batches"))
    assert raised.value.failure_class == "pdf_not_found"
    assert not conversion_log.exists()
