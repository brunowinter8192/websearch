# INFRASTRUCTURE
import pytest

from dev.tests._pdf_fakes import base_manifest, conversion_log, write_manifest
from src.pdf.assemble import assemble_workflow
from src.pdf.fallback import fallback_workflow
from src.pdf.report import WorkflowError
from src.pdf.status import status_workflow

WORKERS = [
    {"name": "tables", "prompt": "prompt_tables.md", "outputs": ["tables/p22_0_fixed.md"]},
    {"name": "pages-21-25", "prompt": "prompt_pages_21-25.md", "pages": [21, 25], "outputs": [f"pages/p{n}_fixed.md" for n in range(21, 26)]},
]
OUTLINED = "done cleverly to disguise the size **an** d distri **b** uti **on** o **f** the costs\n\n## **The market ethic**\n"
PENDING = "<!-- REPAIR PENDING -->"


# FUNCTIONS

def blocked_batch(tmp_path):
    batch_dir = tmp_path / "batch"
    write_manifest(batch_dir, base_manifest(25, workers=WORKERS))
    (batch_dir / "pages").mkdir()
    (batch_dir / "tables").mkdir()
    (batch_dir / "tables" / "p22_0_fixed.md").write_text("|a|\n")
    for number in range(21, 26):
        (batch_dir / "pages" / f"p{number}_outlined.md").write_text(f"Page {number}. {OUTLINED}")
    for number in (21, 22, 23):
        (batch_dir / "pages" / f"p{number}_fixed.md").write_text(f"Page {number}. distribution of the costs\n")
    return batch_dir


def page_status(batch_dir):
    return [line for line in status_workflow(str(batch_dir)).text.splitlines() if "pages-21-25" in line]


def test_a_blocked_page_worker_gets_its_missing_pages_pre_filled_and_an_edit_only_prompt(tmp_path):
    batch_dir = blocked_batch(tmp_path)
    report = fallback_workflow(str(batch_dir), "pages-21-25")
    assert report.ok
    assert "pre-filled from the outlined pages: pages/p24_fixed.md pages/p25_fixed.md" in report.text
    for number in (24, 25):
        assert (batch_dir / "pages" / f"p{number}_fixed.md").read_text() == f"{PENDING}\n\nPage {number}. {OUTLINED}"
    assert (batch_dir / "pages" / "p23_fixed.md").read_text() == "Page 23. distribution of the costs\n"
    prompt = (batch_dir / "prompt_fallback_pages-21-25.md").read_text()
    assert "For each page N in 24, 25:" in prompt and "{{" not in prompt
    assert f"{batch_dir}/pages/pN_fixed.md: the extracted Markdown of the page. This is the file you repair, in place." in prompt
    assert "You are not asked to reproduce, retype or rewrite any content" in prompt
    assert "only with the Edit tool, one small edit at a time" in prompt and "Never use the Write tool" in prompt
    assert f"remove its first line {PENDING} with one last Edit" in prompt


def test_a_pre_filled_page_counts_as_missing_until_the_fallback_worker_removed_its_pending_line(tmp_path, conversion_log):
    batch_dir = blocked_batch(tmp_path)
    assert page_status(batch_dir) == ["  pages-21-25: incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)"]
    fallback_workflow(str(batch_dir), "pages-21-25")
    assert page_status(batch_dir) == ["  pages-21-25: incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)"]
    assert "assemble FAILED (incomplete_worker)" in assemble_workflow(str(batch_dir)).text
    p24 = batch_dir / "pages" / "p24_fixed.md"
    p24.write_text(p24.read_text().replace(f"{PENDING}\n\n", ""))
    assert page_status(batch_dir) == ["  pages-21-25: incomplete (missing: pages/p25_fixed.md)"]
    p25 = batch_dir / "pages" / "p25_fixed.md"
    p25.write_text(p25.read_text().replace(f"{PENDING}\n\n", ""))
    assert page_status(batch_dir) == ["  pages-21-25: complete"]


def test_a_fallback_for_a_worker_that_is_no_page_worker_stops_at_the_tripwire(tmp_path):
    batch_dir = blocked_batch(tmp_path)
    with pytest.raises(WorkflowError) as raised:
        fallback_workflow(str(batch_dir), "tables")
    assert raised.value.failure_class == "fallback_not_observed"
