# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import base_manifest, write_manifest
from src.pdf.sample import sample_workflow
from src.pdf.sample_close import sample_close_workflow
from src.pdf.sample_report import sample_report_workflow

PAGES = 10
SAMPLED = 8
SCHOLTENS_CONTINUATION = (
    "finding that almost all the size-related firm attributes are significantly different at the 1% level. "
    "Institutions that adopted the EP are significantly larger than those that did not."
)
SCHOLTENS = {
    "joined": "As to the CSR characteristics, Table 1 shows a higher score. For the firm characteristics, we have the surprising "
    + SCHOLTENS_CONTINUATION,
    "between": "Table 1. Descriptive statistics and test for equality of means\n\n|Item|Mean|\n|---|---|\n|Assets|12|",
    "sampled": "Table 1 (continued)\n\n|Item|Mean|\n|---|---|\n|Beta|0.9|\n\nSource: Bankscope.",
    "anchor": "Source: Bankscope.",
    "inserted": SCHOLTENS_CONTINUATION,
}
HEILMAYR = {
    "joined": "- Local markets: For each of these mills, we determined the annual capacity of the mill ( $C_{m,t}$ ) and whether "
    "the mill was certified ( $I_{cert_{m,t}}=1$ ). We then calculated the certified proportion of the point’s local market "
    "( $L_{i,t}$ ) using equation (2).",
    "between": "**Figure description (not source text):** A map of Kalimantan with mills.\n\n**Figure 2.** Certified mills in Kalimantan.",
    "sampled": "$$L_{i,t} = \\frac{\\sum C_{m,t}}{\\sum C_{m,t}} \\tag{2}$$\n\nwhere the sums run over the mills of the supply shed.",
    "anchor": "<!-- page 8 -->",
    "inserted": "the mill was certified ( $I_{cert_{m,t}=1}$ ). We then calculated the certified proportion of the point's local "
    "market ( $L_{i,t}$ ) using equation (2).",
}


# FUNCTIONS

def book_with(shape: dict) -> str:
    texts = {page: f"Text {page}. Kostenrechnung auf Seite {page}." for page in range(1, PAGES + 1)}
    texts[SAMPLED - 2] = f"Text {SAMPLED - 2}.\n\n{shape['joined']}"
    texts[SAMPLED - 1] = shape["between"]
    texts[SAMPLED] = shape["sampled"]
    return "\n\n".join(f"<!-- page {page} -->\n\n{texts[page]}" for page in range(1, PAGES + 1)) + "\n"


def opened_with_duplicate(tmp_path, shape: dict):
    batch_dir = tmp_path / "batches" / "Book"
    write_manifest(batch_dir, base_manifest(PAGES))
    (batch_dir / "Book.md").write_text(book_with(shape), encoding="utf-8")
    sample_workflow(str(batch_dir))
    run_dir = batch_dir / "samples" / "run_1"
    run = json.loads((run_dir / "run.json").read_text())
    assert run["pages"] == [SAMPLED]
    (excerpt,) = run["excerpts"]
    path = run_dir / excerpt["file"]
    path.write_text(path.read_text().replace(shape["anchor"], shape["anchor"] + "\n\n" + shape["inserted"], 1))
    (run_dir / "findings.md").write_text(f"page {SAMPLED}: missing_text: opening text of the page missing, added\n")
    return batch_dir, run_dir, excerpt


@pytest.mark.parametrize("shape", [SCHOLTENS, HEILMAYR], ids=["scholtens_8_10", "heilmayr_7_9"])
def test_report_marks_an_insertion_that_already_ends_a_paragraph_on_an_earlier_page(tmp_path, shape):
    batch_dir, run_dir, excerpt = opened_with_duplicate(tmp_path, shape)
    report = sample_report_workflow(str(batch_dir))
    assert f"duplicates of earlier text, rejected at close: {excerpt['file']}" in report.text
    text = (run_dir / "report.md").read_text()
    assert f"DUPLICATE: the inserted text already ends a paragraph on page {SAMPLED - 2}, before this excerpt." in text


@pytest.mark.parametrize("shape", [SCHOLTENS, HEILMAYR], ids=["scholtens_8_10", "heilmayr_7_9"])
def test_close_rejects_the_duplicate_insertion_and_the_loop_ends(tmp_path, shape):
    batch_dir, run_dir, excerpt = opened_with_duplicate(tmp_path, shape)
    before = (batch_dir / "Book.md").read_text()
    report = sample_close_workflow(str(batch_dir), [])
    assert "corrections applied 0, rejected 1" in report.text
    assert f"rejected as duplicate of earlier text: {excerpt['file']}" in report.text
    assert "loop ended: run 1 applied no correction" in report.text
    assert (batch_dir / "Book.md").read_text() == before
    closed = json.loads((run_dir / "run.json").read_text())
    assert closed["applied"] == [] and closed["duplicates"] == [excerpt["file"]] and closed["rejected"] == [excerpt["file"]]
