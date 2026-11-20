# INFRASTRUCTURE
import re

import pytest

from dev.tests._pdf_fakes import base_manifest, conversion_log, read_log, write_manifest
from src.pdf.assemble import assemble_workflow
from src.pdf.report import WorkflowError

TABLE = "|a|b|\n|---|---|\n|1|2|"
FIGURE = "**Figure description (not source text):** Line chart of the CAR."


# FUNCTIONS

def batch(tmp_path, pages, tables=(), figures=()):
    batch_dir = tmp_path / "batch"
    outputs = [f"pages/p{number}_fixed.md" for number in range(1, len(pages) + 1)]
    workers = [{"name": "pages", "prompt": "prompt_pages.md", "outputs": outputs}]
    workers += [{"name": "tables", "prompt": "prompt_tables.md", "outputs": [f"tables/{name}_fixed.md" for name in tables]}]
    workers += [{"name": "figures", "prompt": "prompt_figures.md", "outputs": [f"figures/{name}_fixed.md" for name in figures]}]
    manifest = base_manifest(len(pages), workers=workers)
    manifest["tables"], manifest["figures"] = list(tables), list(figures)
    write_manifest(batch_dir, manifest)
    for name in ("pages", "tables", "figures"):
        (batch_dir / name).mkdir()
    for number, text in enumerate(pages, start=1):
        (batch_dir / "pages" / f"p{number}_outlined.md").write_text(text)
        (batch_dir / "pages" / f"p{number}_fixed.md").write_text(text)
    for name in tables:
        (batch_dir / "tables" / f"{name}_fixed.md").write_text(TABLE + "\n")
    for name in figures:
        (batch_dir / "figures" / f"{name}_fixed.md").write_text(FIGURE + "\n")
    return batch_dir


def book_pages(batch_dir):
    book = (batch_dir / "Book.md").read_text()
    parts = re.split(r"^<!-- page \d+ -->$", book, flags=re.MULTILINE)
    return [part.strip() for part in parts[1:]]


def test_a_paragraph_running_over_the_page_is_completed_before_the_footnotes_of_its_page(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "## 1. INTRODUCTION \n\nHeal (2005, p. 393) defines CSR as ‘‘(. . .) taking actions which reduce the extent of externalized \n\n"
        "[^*]: We are very grateful to the editor. Final revision accepted: October 16, 2006.\n",
        "costs or avoid distributional conflicts.’’ Furthermore, we want to find out more.\n\nThe structure of this paper is as follows.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert report.ok
    assert "page joins: 1: 1->2(body)" in report.text
    first, second = book_pages(batch_dir)
    assert first.split("\n\n") == [
        "## 1. INTRODUCTION",
        "Heal (2005, p. 393) defines CSR as “(. . .) taking actions which reduce the extent of externalized "
        "costs or avoid distributional conflicts.” Furthermore, we want to find out more.",
        "[^*]: We are very grateful to the editor. Final revision accepted: October 16, 2006.",
    ]
    assert second == "The structure of this paper is as follows."
    assert (batch_dir / "Book.md").read_text().startswith("<!-- page 1 -->\n\n## 1. INTRODUCTION")


def test_a_new_paragraph_at_the_top_of_the_next_page_stays_on_that_page(tmp_path):
    batch_dir = batch(tmp_path, [
        "In high-impact projects, borrowers develop an EMP that addresses mitigation and monitoring of\n",
        "environmental and social risk. Adopters are required to report on an annual basis.[^2]\n\n"
        "The history of the EP is described by Esty, Knoop, and Sesia (2005).\n",
    ])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first.endswith("mitigation and monitoring of environmental and social risk. Adopters are required to report on an annual basis.[^2]")
    assert second == "The history of the EP is described by Esty, Knoop, and Sesia (2005)."


def test_a_word_hyphenated_over_the_page_boundary_is_joined_without_hyphen_and_space(tmp_path):
    batch_dir = batch(tmp_path, ["It may increase the ben-\n", "efits. Furthermore, apart from that.\n\n### (c) Governance issues\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "It may increase the benefits. Furthermore, apart from that."
    assert second == "### (c) Governance issues"


def test_a_footnote_running_over_the_page_takes_the_unmarked_continuation(tmp_path):
    batch_dir = batch(tmp_path, [
        "Further research will be needed to address these issues.\n\n## NOTES\n\n[^1]: IFC uses a set of policies for private sector\n",
        "projects. The safeguard policies provide guidance.\n\n[^2]: From March to May 2006, the EP banks engaged in a review.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "1->2(footnote)" in report.text
    first, second = book_pages(batch_dir)
    assert first.endswith("[^1]: IFC uses a set of policies for private sector projects. The safeguard policies provide guidance.")
    assert second == "[^2]: From March to May 2006, the EP banks engaged in a review."


def test_the_join_skips_a_page_of_table_caption_table_and_note_and_a_table_caption_and_note_on_the_next(tmp_path):
    batch_dir = batch(tmp_path, [
        "For the firm characteristics, we have the surprising\n",
        "Table 1. Descriptive statistics\n\n<!-- TABLE p2_0 -->\n\n(continued on next page)\n",
        "Table 1—continued\n\n<!-- TABLE p3_0 -->\n\nSource: Bankscope, Datastream.\n\nfinding that almost all attributes differ.\n\nNext paragraph.\n",
    ], tables=("p2_0", "p3_0"))
    report = assemble_workflow(str(batch_dir))
    assert "1->3(body)" in report.text
    first, second, third = book_pages(batch_dir)
    assert first == "For the firm characteristics, we have the surprising finding that almost all attributes differ."
    assert second == f"Table 1. Descriptive statistics\n\n{TABLE}\n\n(continued on next page)"
    assert third == f"Table 1—continued\n\n{TABLE}\n\nSource: Bankscope, Datastream.\n\nNext paragraph."


def test_the_join_skips_a_figure_and_its_caption(tmp_path):
    batch_dir = batch(tmp_path, [
        "the cumulative abnormal returns for the period of one day before the event\n",
        "<!-- FIGURE p2_0 -->\n\nFigure 3. Cumulative abnormal returns.\n\nuntil one day after the event.\n",
    ], figures=("p2_0",))
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "the cumulative abnormal returns for the period of one day before the event until one day after the event."
    assert second == f"{FIGURE}\n\nFigure 3. Cumulative abnormal returns."


def test_a_page_number_left_in_the_page_is_neither_joined_onto_nor_moved(tmp_path):
    batch_dir = batch(tmp_path, ["which reduce the extent of externalized\n\n1307\n", "iii\n\ncosts or avoid conflicts.\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "which reduce the extent of externalized costs or avoid conflicts.\n\n1307"
    assert second == "iii"


def test_a_finished_paragraph_and_a_heading_on_the_next_page_are_not_joined(tmp_path):
    batch_dir = batch(tmp_path, ["The model specification is linear:\n", "Here, Ri is the daily return.\n", "of the\n", "## REFERENCES\n\nmore text\n"])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 0: none" in report.text
    assert book_pages(batch_dir) == ["The model specification is linear:", "Here, Ri is the daily return.", "of the", "## REFERENCES\n\nmore text"]


def test_an_incomplete_worker_stops_assemble_with_the_missing_files_and_logs_it(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["a.\n", "b.\n"])
    (batch_dir / "pages" / "p2_fixed.md").unlink()
    report = assemble_workflow(str(batch_dir))
    assert not report.ok
    assert report.text.splitlines() == [
        "assemble FAILED (incomplete_worker): 1 of 3 workers incomplete, nothing written",
        "  pages: incomplete (missing: pages/p2_fixed.md)",
    ]
    assert not (batch_dir / "Book.md").exists()
    end = read_log(conversion_log)[-1]
    assert (end["outcome"], end["failure_class"]) == ("failed", "incomplete_worker")
    assert end["incomplete_workers"] == [{"name": "pages", "missing": ["pages/p2_fixed.md"]}]


def test_a_page_worker_that_dropped_a_table_placeholder_fails_assemble(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["Table 1.\n\n<!-- TABLE p1_0 -->\n"], tables=("p1_0",))
    (batch_dir / "pages" / "p1_fixed.md").write_text("Table 1.\n")
    report = assemble_workflow(str(batch_dir))
    assert not report.ok
    assert "assemble FAILED (placeholder_changed): page 1" in report.text and "TABLE p1_0" in report.text
    assert read_log(conversion_log)[-1]["failure_class"] == "placeholder_changed"


def test_assemble_before_apply_outline_fails(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["a.\n"])
    (batch_dir / "pages" / "p1_outlined.md").unlink()
    report = assemble_workflow(str(batch_dir))
    assert "assemble FAILED (outline_not_applied)" in report.text


def test_assemble_after_sampling_started_is_refused(tmp_path):
    batch_dir = batch(tmp_path, ["a.\n"])
    (batch_dir / "samples" / "run_1").mkdir(parents=True)
    (batch_dir / "samples" / "run_1" / "run.json").write_text('{"run": 1, "status": "open"}')
    with pytest.raises(WorkflowError) as raised:
        assemble_workflow(str(batch_dir))
    assert raised.value.failure_class == "sampling_started"
