# INFRASTRUCTURE
from pathlib import Path

from src.pdf.extract import batch_entry, render_prompt

PDF = Path("/data/pdf/Book.pdf")
BATCH_DIR = Path("/tmp/pdf_Book")


# FUNCTIONS

def test_forty_page_batch_reads_twice_and_assembles_from_parts():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(41, 80))
    assert 'pages parameter "41-60"' in prompt
    assert 'pages parameter "61-80"' in prompt
    assert "/tmp/pdf_Book/part1_41-80.md" in prompt
    assert "/tmp/pdf_Book/part2_41-80.md" in prompt
    assert '> "/tmp/pdf_Book/batch_41-80.md"' in prompt
    assert "Anchor text: /tmp/pdf_Book/anchor_41-80.md" in prompt
    assert "Output file: /tmp/pdf_Book/batch_41-80.md" in prompt
    assert "{{" not in prompt


def test_short_last_batch_splits_at_twenty_pages():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(961, 993))
    assert 'pages parameter "961-980"' in prompt
    assert 'pages parameter "981-993"' in prompt


def test_batch_up_to_twenty_pages_reads_once_and_writes_the_output_directly():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 20))
    assert prompt.count("pages parameter") == 1
    assert 'pages parameter "1-20"' in prompt
    assert "part1_" not in prompt
    assert "cat " not in prompt


def test_single_page_batch_uses_a_bare_page_number():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(41, 41))
    assert 'pages parameter "41"' in prompt
    assert 'pages parameter "41-41"' not in prompt


def test_prompt_asks_for_figure_descriptions_and_keeps_no_placeholder_rule():
    prompt = render_prompt(PDF, BATCH_DIR, batch_entry(1, 40))
    assert "write a text description" in prompt
    assert "every label and every box text" in prompt
    assert "Never drop a figure" in prompt
    assert "image placeholders" not in prompt
