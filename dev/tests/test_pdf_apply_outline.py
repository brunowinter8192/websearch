# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import base_manifest, write_manifest
from src.pdf.apply_outline import apply_outline_workflow
from src.pdf.report import WorkflowError

HEADINGS = [
    {"id": "h1_0", "page": 1, "text": "## Banking on the Equator"},
    {"id": "h1_1", "page": 1, "text": "#### 1. INTRODUCTION"},
    {"id": "h2_0", "page": 2, "text": "#### Ri ¼ a þ bRm þ error:"},
]
PAGES = {
    1: "<!-- HEADING h1_0 -->\n\nBERT SCHOLTENS \n\n<!-- HEADING h1_1 -->\n\nOn June 4, 2003, banks announced.\n",
    2: "<!-- FIGURE p2_0 -->\n\n<!-- HEADING h2_0 -->\n\nHere, Ri is the daily return.\n\n(a) Descriptives and t-test of equality of means \n\nThe hypotheses.\n",
}
OUTLINE = {
    "headings": [
        {"id": "h1_0", "level": 1, "text": "Banking on the Equator"},
        {"id": "h1_1", "level": 2, "text": "1. INTRODUCTION"},
        {"id": "h2_0", "level": 0, "text": "### Ri ¼ a þ bRm þ error:"},
    ],
    "missed": [{"page": 2, "line": "(a) Descriptives and t-test of equality of means ", "level": 3}],
}


# FUNCTIONS

def batch(tmp_path, outline=OUTLINE):
    batch_dir = tmp_path / "batch"
    write_manifest(batch_dir, base_manifest(2, workers=[{"name": "outline", "prompt": "prompt_outline.md", "outputs": ["headings_fixed.json"]}]))
    (batch_dir / "pages").mkdir()
    for number, text in PAGES.items():
        (batch_dir / "pages" / f"p{number}.md").write_text(text)
    (batch_dir / "headings.json").write_text(json.dumps(HEADINGS, ensure_ascii=False))
    if outline is not None:
        (batch_dir / "headings_fixed.json").write_text(json.dumps(outline, ensure_ascii=False))
    return batch_dir


def outlined(batch_dir, number):
    return (batch_dir / "pages" / f"p{number}_outlined.md").read_text()


def test_levels_from_the_outline_replace_the_heading_placeholders(tmp_path):
    batch_dir = batch(tmp_path)
    report = apply_outline_workflow(str(batch_dir))
    assert report.ok
    assert outlined(batch_dir, 1) == "# Banking on the Equator\n\nBERT SCHOLTENS \n\n## 1. INTRODUCTION\n\nOn June 4, 2003, banks announced.\n"
    assert "apply-outline ok: 3 headings, 1 set to level 0, 1 missed headings added" in report.text
    assert report.text.splitlines()[-3:] == ["  # Banking on the Equator", "  ## 1. INTRODUCTION", "  ### (a) Descriptives and t-test of equality of means"]


def test_level_zero_keeps_the_line_as_text_without_heading_marks_and_figures_stay(tmp_path):
    batch_dir = batch(tmp_path)
    apply_outline_workflow(str(batch_dir))
    page = outlined(batch_dir, 2)
    assert page.startswith("<!-- FIGURE p2_0 -->\n\nRi ¼ a þ bRm þ error:\n\nHere, Ri")
    assert "\n\n### (a) Descriptives and t-test of equality of means\n\nThe hypotheses." in page


def test_the_extracted_page_files_stay_untouched_so_a_second_run_gives_the_same_result(tmp_path):
    batch_dir = batch(tmp_path)
    apply_outline_workflow(str(batch_dir))
    first = outlined(batch_dir, 2)
    assert apply_outline_workflow(str(batch_dir)).ok
    assert outlined(batch_dir, 2) == first
    assert (batch_dir / "pages" / "p2.md").read_text() == PAGES[2]


def test_a_missed_line_that_is_not_in_the_page_file_fails_with_page_and_line(tmp_path):
    outline = dict(OUTLINE, missed=[{"page": 2, "line": "APPENDIX A. LIST OF BANKS", "level": 2}])
    with pytest.raises(WorkflowError) as raised:
        apply_outline_workflow(str(batch(tmp_path, outline)))
    assert raised.value.failure_class == "missed_heading_not_found"
    assert "page 2" in str(raised.value) and "APPENDIX A. LIST OF BANKS" in str(raised.value)
    assert not (tmp_path / "batch" / "pages" / "p1_outlined.md").exists()


def test_without_a_complete_outline_nothing_is_applied(tmp_path):
    with pytest.raises(WorkflowError) as raised:
        apply_outline_workflow(str(batch(tmp_path, outline=None)))
    assert raised.value.failure_class == "outline_incomplete"
