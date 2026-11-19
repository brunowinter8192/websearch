# INFRASTRUCTURE
from pathlib import Path

from src.pdf.pieces import piece_entry, render_prompt

PDF = Path("/data/pdf/Book.pdf")
BATCH_DIR = Path("/tmp/pdf_Book")


# FUNCTIONS

def numbered_steps(prompt):
    return [line for line in prompt.splitlines() if line[:2].rstrip(".").isdigit()]


def test_fifty_page_piece_reads_three_times_and_joins_three_parts_into_the_piece_file():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(51, 100))
    assert prompt.count("pages parameter") == 3
    for pages in ("51-70", "71-90", "91-100"):
        assert f'pages parameter "{pages}"' in prompt
    for number in (1, 2, 3):
        assert f"/tmp/pdf_Book/part{number}_51-100.md" in prompt
    assert "part4_" not in prompt
    assert prompt.count('cat "') == 3
    assert '> "/tmp/pdf_Book/piece_51-100.md" && rm' in prompt
    assert "Output file: /tmp/pdf_Book/piece_51-100.md" in prompt
    assert "Pages of this piece: 51-100" in prompt
    assert "{{" not in prompt


def test_steps_start_at_one_and_each_read_precedes_its_write():
    steps = numbered_steps(render_prompt(PDF, BATCH_DIR, piece_entry(1, 50)))
    assert [line.split(".")[0] for line in steps] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert steps[0].startswith("1. Read the PDF pages 1-20")
    assert steps[1].startswith("2. Write the Markdown for pages 1-20 to the part file /tmp/pdf_Book/part1_1-50.md")
    assert steps[6].startswith("7. Create the output file")
    assert steps[7].startswith("8. When the output file exists")


def test_prompt_has_no_anchor_and_names_the_page_images_as_the_only_source():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(1, 50))
    assert "Anchor text:" not in prompt and "anchor_" not in prompt and "Read the anchor" not in prompt
    assert "The page images are the only source" in prompt
    assert "[?]" in prompt


def test_piece_of_twenty_pages_reads_once_and_writes_the_piece_file_directly():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(21, 40))
    assert prompt.count("pages parameter") == 1
    assert 'pages parameter "21-40"' in prompt
    assert "part1_" not in prompt and "cat " not in prompt
    assert numbered_steps(prompt)[0].startswith("1. Read the PDF pages 21-40")


def test_piece_of_twenty_one_pages_ends_with_a_single_page_read():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(1, 21))
    assert 'pages parameter "1-20"' in prompt
    assert 'pages parameter "21"' in prompt
    assert '"21-21"' not in prompt


def test_single_page_piece_uses_a_bare_page_number():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(51, 51))
    assert 'pages parameter "51"' in prompt
    assert "Output file: /tmp/pdf_Book/piece_51-51.md" in prompt


def test_prompt_carries_the_form_rules():
    prompt = render_prompt(PDF, BATCH_DIR, piece_entry(1, 50))
    assert "stays one paragraph" in prompt
    assert "never inside a sentence" in prompt
    assert "title of the work #, chapter ##, subchapter ###" in prompt
    assert "outline.md" in prompt
    assert "**Figure description (not source text):**" in prompt
    assert "every label and every box text" in prompt
    assert "Never drop a figure" in prompt
    assert "footnote mark in the text as [^N]" in prompt
    assert "Never write a Markdown image link" in prompt
    assert "Never mix straight and typographic quotation marks" in prompt
    assert "For a page without content write only this line" in prompt
