# INFRASTRUCTURE
import json

from dev.tests._pdf_fakes import base_manifest, write_manifest
from src.pdf.status import status_workflow

WORKERS = [
    {"name": "tables", "prompt": "prompt_tables.md", "outputs": ["tables/p9_0_fixed.md", "tables/p10_0_fixed.md"]},
    {"name": "outline", "prompt": "prompt_outline.md", "outputs": ["headings_fixed.json"]},
    {"name": "pages-1-5", "prompt": "prompt_pages_1-5.md", "outputs": [f"pages/p{n}_fixed.md" for n in range(1, 6)]},
    {"name": "pages-6-7", "prompt": "prompt_pages_6-7.md", "outputs": ["pages/p6_fixed.md", "pages/p7_fixed.md"]},
]
HEADINGS = [{"id": "h1_0", "page": 1, "text": "# Title"}, {"id": "h2_0", "page": 2, "text": "## 1. INTRODUCTION"}]


# FUNCTIONS

def batch(tmp_path):
    batch_dir = tmp_path / "batch"
    write_manifest(batch_dir, base_manifest(7, workers=WORKERS))
    for name in ("tables", "pages"):
        (batch_dir / name).mkdir()
    (batch_dir / "headings.json").write_text(json.dumps(HEADINGS))
    return batch_dir


def write(batch_dir, *names):
    for name in names:
        (batch_dir / name).write_text("text\n")


def outline(levels, missed=()):
    return json.dumps({"headings": [{"id": i, "level": level, "text": "x"} for i, level in levels], "missed": list(missed)})


def test_every_worker_is_complete_when_all_its_files_exist(tmp_path):
    batch_dir = batch(tmp_path)
    write(batch_dir, *[name for worker in WORKERS if worker["name"] != "outline" for name in worker["outputs"]])
    (batch_dir / "headings_fixed.json").write_text(outline([("h1_0", 1), ("h2_0", 0)]))
    report = status_workflow(str(batch_dir))
    assert report.ok
    assert report.text.splitlines() == [
        "workers complete: 4 of 4",
        "  tables: complete",
        "  outline: complete",
        "  pages-1-5: complete",
        "  pages-6-7: complete",
    ]


def test_a_worker_that_wrote_nothing_or_only_part_is_incomplete_with_the_missing_files(tmp_path):
    batch_dir = batch(tmp_path)
    write(batch_dir, "tables/p9_0_fixed.md", "pages/p1_fixed.md", "pages/p2_fixed.md", "pages/p6_fixed.md", "pages/p7_fixed.md")
    lines = status_workflow(str(batch_dir)).text.splitlines()
    assert lines == [
        "workers complete: 1 of 4",
        "  tables: incomplete (missing: tables/p10_0_fixed.md)",
        "  outline: incomplete (missing: headings_fixed.json)",
        "  pages-1-5: incomplete (missing: pages/p3_fixed.md pages/p4_fixed.md pages/p5_fixed.md)",
        "  pages-6-7: complete",
    ]


def test_an_outline_file_that_is_not_json_or_lacks_a_heading_id_is_incomplete(tmp_path):
    batch_dir = batch(tmp_path)
    for content in ('{"headings": [', outline([("h1_0", 1)]), json.dumps({"headings": []})):
        (batch_dir / "headings_fixed.json").write_text(content)
        assert "  outline: incomplete (missing: headings_fixed.json)" in status_workflow(str(batch_dir)).text
