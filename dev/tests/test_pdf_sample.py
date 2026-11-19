# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, write_pdf, write_pieces
from src.pdf.merge import merge_workflow
from src.pdf.report import WorkflowError
from src.pdf.sample import cut_excerpts, draw_sample_pages, sample_workflow
from src.pdf.split import split_workflow

SHA = "a" * 64


# FUNCTIONS

def merged(tmp_path, pages):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(pages))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    write_pieces(batch_dir)
    merge_workflow(str(batch_dir))
    return batch_dir


def manifest_of(pages):
    return {"pages": pages, "pdf_sha256": SHA}


def book_of(pages, missing=()):
    return "".join(f"<!-- page {page} -->\n\nText {page}.\n\n" for page in pages if page not in missing)


def test_a_run_draws_ten_percent_rounded_up_per_fifty_page_block():
    pages = draw_sample_pages(manifest_of(85), [])
    assert len([page for page in pages if page <= 50]) == 5
    assert len([page for page in pages if page > 50]) == 4
    assert pages == sorted(set(pages))


def test_a_nine_page_pdf_gets_one_page_per_run():
    assert len(draw_sample_pages(manifest_of(9), [])) == 1


def test_a_later_run_draws_only_pages_never_sampled_before():
    first = draw_sample_pages(manifest_of(85), [])
    second = draw_sample_pages(manifest_of(85), [{"pages": first}])
    assert len(second) == 9
    assert not set(first) & set(second)


def test_runs_run_out_of_pages_when_every_page_was_sampled_once():
    runs = []
    while len(runs) < 20:
        pages = draw_sample_pages(manifest_of(9), runs)
        if not pages:
            break
        runs.append({"pages": pages})
    assert len(runs) == 9
    assert sorted(page for run in runs for page in run["pages"]) == list(range(1, 10))


def test_the_draw_is_the_same_for_the_same_pdf_and_run():
    assert draw_sample_pages(manifest_of(500), []) == draw_sample_pages(manifest_of(500), [])
    assert draw_sample_pages(manifest_of(500), []) != draw_sample_pages({"pages": 500, "pdf_sha256": "b" * 64}, [])


def test_an_excerpt_runs_from_the_marker_of_the_page_before_to_the_marker_of_the_page_after():
    book = book_of(range(1, 6))
    (excerpt,) = cut_excerpts(book, [3])
    assert excerpt["original"] == "<!-- page 2 -->\n\nText 2.\n\n<!-- page 3 -->\n\nText 3.\n\n"
    assert excerpt["file"] == "excerpt_3.md"
    assert book[excerpt["start"]:excerpt["end"]] == excerpt["original"]


def test_first_and_last_page_excerpts_reach_the_ends_of_the_book():
    book = book_of(range(1, 6))
    first, last = cut_excerpts(book, [1, 5])
    assert first["original"] == "<!-- page 1 -->\n\nText 1.\n\n"
    assert last["original"] == "<!-- page 4 -->\n\nText 4.\n\n<!-- page 5 -->\n\nText 5.\n\n"


def test_neighbouring_sample_pages_share_one_excerpt():
    (excerpt,) = cut_excerpts(book_of(range(1, 6)), [3, 4])
    assert excerpt["pages"] == [3, 4]
    assert excerpt["file"] == "excerpt_3-4.md"
    assert excerpt["original"].startswith("<!-- page 2 -->") and "<!-- page 5 -->" not in excerpt["original"]


def test_a_sample_page_without_its_marker_gets_the_text_between_its_neighbours():
    (excerpt,) = cut_excerpts(book_of(range(1, 6), missing=(3,)), [3])
    assert excerpt["original"] == "<!-- page 2 -->\n\nText 2.\n\n"


def test_sample_opens_a_run_with_excerpt_files_run_file_and_prompt(tmp_path, conversion_log):
    batch_dir = merged(tmp_path, 85)
    report = sample_workflow(str(batch_dir))
    assert report.ok
    run_dir = batch_dir / "samples" / "run_1"
    run = json.loads((run_dir / "run.json").read_text())
    assert run["status"] == "open" and len(run["pages"]) == 9
    book = (batch_dir / "Book.md").read_text()
    for excerpt in run["excerpts"]:
        assert (run_dir / excerpt["file"]).read_text() == book[excerpt["start"]:excerpt["end"]]
    prompt = (run_dir / "prompt.md").read_text()
    assert "{{" not in prompt
    assert "Pages to check: " + " ".join(str(page) for page in run["pages"]) in prompt
    assert f"Findings file: {run_dir / 'findings.md'}" in prompt
    first = run["excerpts"][0]
    assert f"1. Read the excerpt file {run_dir / first['file']} completely" in prompt
    assert f'pages parameter "{first["pages"][0]}' in prompt
    assert "Never change, add or remove a line <!-- page N -->" in prompt
    assert "pages sampled after this run: 9 of 85" in report.text


def test_a_second_run_cannot_be_opened_while_one_is_open(tmp_path, conversion_log):
    batch_dir = merged(tmp_path, 20)
    sample_workflow(str(batch_dir))
    with pytest.raises(WorkflowError) as raised:
        sample_workflow(str(batch_dir))
    assert raised.value.failure_class == "run_open"
