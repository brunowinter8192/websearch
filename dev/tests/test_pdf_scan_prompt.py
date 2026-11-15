# INFRASTRUCTURE
from pathlib import Path

from src.pdf.extract import batch_entry, render_control_prompt, render_prompt

PDF = Path("/data/pdf/Scan.pdf")
BATCH_DIR = Path("/tmp/pdf_Scan")


# FUNCTIONS

def numbered_steps(prompt):
    return [line for line in prompt.splitlines() if line[:2].rstrip(".").isdigit()]


def test_scan_prompt_for_a_fifty_page_batch_has_no_anchor_and_starts_reading_at_step_one():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(51, 100, "scan"), "scan")
    assert "Anchor text:" not in prompt and "anchor_" not in prompt and "Read the anchor" not in prompt
    assert "{{" not in prompt
    assert "no text layer" in prompt
    steps = numbered_steps(prompt)
    assert [line.split(".")[0] for line in steps] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert steps[0].startswith("1. Read the PDF pages 51-70")
    assert steps[1].startswith("2. Write the Markdown for pages 51-70 to the part file /tmp/pdf_Scan/part1_51-100.md")
    assert steps[6].startswith("7. Create the output file")
    assert '> "/tmp/pdf_Scan/batch_51-100.md" && rm' in prompt


def test_scan_prompt_for_a_short_batch_reads_once_and_writes_directly():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 9, "scan"), "scan")
    assert prompt.count("pages parameter") == 1
    assert 'pages parameter "1-9"' in prompt
    assert "part1_" not in prompt and "cat " not in prompt
    assert numbered_steps(prompt)[0].startswith("1. Read the PDF pages 1-9")


def test_control_prompt_lists_every_page_with_its_batch_file_and_the_control_json_path():
    entries = [batch_entry(1, 50, "scan"), batch_entry(51, 85, "scan")]
    prompt = render_control_prompt(PDF, BATCH_DIR, entries, [4, 37, 60])
    assert "{{" not in prompt
    assert "Pages to check: 4 37 60" in prompt
    assert "/tmp/pdf_Scan/batch_1-50.md /tmp/pdf_Scan/batch_51-85.md" in prompt
    assert "Output file: /tmp/pdf_Scan/control.json" in prompt
    steps = numbered_steps(prompt)
    assert [line.split(".")[0] for line in steps] == ["1", "2", "3", "4", "5", "6"]
    assert steps[1].startswith('2. Read PDF page 4 with the Read tool (pages parameter "4")')
    assert "/tmp/pdf_Scan/batch_1-50.md" in steps[1]
    assert steps[3].startswith('4. Read PDF page 60')
    assert "/tmp/pdf_Scan/batch_51-85.md" in steps[3]
    assert steps[4].startswith("5. Write your findings")
    assert "marker_missing" in prompt


def test_control_prompt_names_only_batch_files_that_hold_a_control_page():
    entries = [batch_entry(1, 50, "scan"), batch_entry(51, 85, "scan")]
    prompt = render_control_prompt(PDF, BATCH_DIR, entries, [60])
    assert "/tmp/pdf_Scan/batch_51-85.md" in prompt
    assert "/tmp/pdf_Scan/batch_1-50.md" not in prompt
