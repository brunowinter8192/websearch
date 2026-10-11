# INFRASTRUCTURE
from pathlib import Path

from src.pdf.extract import batch_entry, render_prompt

PDF = Path("/data/pdf/Book.pdf")
BATCH_DIR = Path("/tmp/pdf_Book")


# FUNCTIONS

def test_fifty_page_batch_reads_three_times_and_assembles_from_three_parts():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(51, 100))
    assert prompt.count("pages parameter") == 3
    assert 'pages parameter "51-70"' in prompt
    assert 'pages parameter "71-90"' in prompt
    assert 'pages parameter "91-100"' in prompt
    for number in (1, 2, 3):
        assert f"/tmp/pdf_Book/part{number}_51-100.md" in prompt
    assert "part4_" not in prompt
    assert prompt.count("cat \"") == 3
    assert '> "/tmp/pdf_Book/batch_51-100.md" && rm' in prompt
    assert "Anchor text: /tmp/pdf_Book/anchor_51-100.md" in prompt
    assert "Output file: /tmp/pdf_Book/batch_51-100.md" in prompt
    assert "{{" not in prompt


def test_steps_are_numbered_in_order_and_each_read_precedes_its_write():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 50))
    steps = [line for line in prompt.splitlines() if line[:2].rstrip(".").isdigit()]
    assert [line.split(".")[0] for line in steps] == ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    assert steps[1].startswith("2. Read the PDF pages 1-20")
    assert steps[2].startswith("3. Write the Markdown for pages 1-20 to the part file /tmp/pdf_Book/part1_1-50.md")
    assert steps[7].startswith("8. Create the output file")
    assert steps[8].startswith("9. When the output file exists")


def test_last_batch_of_a_book_splits_at_twenty_pages():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(951, 993))
    assert 'pages parameter "951-970"' in prompt
    assert 'pages parameter "971-990"' in prompt
    assert 'pages parameter "991-993"' in prompt


def test_batch_of_twenty_one_pages_ends_with_a_single_page_read():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 21))
    assert 'pages parameter "1-20"' in prompt
    assert 'pages parameter "21"' in prompt
    assert '"21-21"' not in prompt


def test_batch_up_to_twenty_pages_reads_once_and_writes_the_output_directly():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 20))
    assert prompt.count("pages parameter") == 1
    assert 'pages parameter "1-20"' in prompt
    assert "part1_" not in prompt
    assert "cat " not in prompt


def test_single_page_batch_uses_a_bare_page_number():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(51, 51))
    assert 'pages parameter "51"' in prompt
    assert 'pages parameter "51-51"' not in prompt


def test_prompt_asks_for_figure_descriptions_and_keeps_no_placeholder_rule():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 50))
    assert "write a text description" in prompt
    assert "every label and every box text" in prompt
    assert "Never drop a figure" in prompt
    assert "image placeholders" not in prompt
