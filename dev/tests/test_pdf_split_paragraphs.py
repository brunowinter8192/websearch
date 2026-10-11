# INFRASTRUCTURE
import re

from src.config import PARAGRAPH_LIMIT_BYTES
from src.pdf.assemble import split_long_paragraphs

PARAGRAPH_BREAK = re.compile(r"\n{2,}")


# FUNCTIONS

def size(text):
    return len(text.encode("utf-8"))


def squeeze(text):
    return re.sub(r"\s+", "", text)


def paragraphs_of(text):
    return PARAGRAPH_BREAK.split(text)


def prose(sentences):
    return " ".join(f"Satz {number} über Äpfel und Größen für die Prüfung." for number in range(sentences))


def table(rows, cell="Wert"):
    lines = ["| Nr | Bezeichnung |", "|---|---|"] + [f"| {number} | {cell} {number} |" for number in range(rows)]
    return "\n".join(lines)


def test_limit_is_nine_hundred_bytes():
    assert PARAGRAPH_LIMIT_BYTES == 900


def test_short_paragraphs_and_their_separators_stay_byte_identical():
    book = "Erster Absatz.\n\nZweiter Absatz.\n\n\n\nDritter Absatz."
    result = split_long_paragraphs(book)
    assert result.text == book
    assert (result.paragraphs_split, result.tables_split, result.paragraphs_over_limit) == (0, 0, 0)


def test_long_prose_splits_at_sentence_ends_and_keeps_the_text():
    original = prose(40)
    result = split_long_paragraphs("Davor.\n\n" + original + "\n\nDanach.")
    chunks = paragraphs_of(result.text)
    assert chunks[0] == "Davor." and chunks[-1] == "Danach."
    body = chunks[1:-1]
    assert len(body) > 1
    assert all(size(chunk) <= PARAGRAPH_LIMIT_BYTES for chunk in body)
    assert all(chunk.endswith(".") for chunk in body)
    assert squeeze("".join(body)) == squeeze(original)
    assert result.paragraphs_split == 1 and result.tables_split == 0


def test_limit_counts_bytes_not_characters():
    original = "ä " * 400
    assert len(original) < 1000 and size(original) > 1000
    result = split_long_paragraphs(original.strip())
    chunks = paragraphs_of(result.text)
    assert len(chunks) > 1
    assert all(size(chunk) <= PARAGRAPH_LIMIT_BYTES for chunk in chunks)
    assert " ".join(chunks).split() == original.split()


def test_prose_without_sentence_ends_splits_at_spaces_never_inside_a_word():
    words = [f"Wort{number}" for number in range(300)]
    result = split_long_paragraphs(" ".join(words))
    chunks = paragraphs_of(result.text)
    assert len(chunks) > 1
    assert all(size(chunk) <= PARAGRAPH_LIMIT_BYTES for chunk in chunks)
    assert [word for chunk in chunks for word in chunk.split(" ")] == words


def test_list_block_splits_between_lines_without_changing_a_line():
    lines = [f"- Punkt {number} der Aufzählung mit etwas Text zur Länge" for number in range(30)]
    result = split_long_paragraphs("\n".join(lines))
    chunks = paragraphs_of(result.text)
    assert len(chunks) > 1
    assert all(size(chunk) <= PARAGRAPH_LIMIT_BYTES for chunk in chunks)
    assert [line for chunk in chunks for line in chunk.split("\n")] == lines


def test_table_splits_between_rows_and_repeats_header_and_rule():
    original = table(60)
    result = split_long_paragraphs(original)
    chunks = paragraphs_of(result.text)
    original_rows = original.split("\n")[2:]
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.split("\n")[:2] == ["| Nr | Bezeichnung |", "|---|---|"]
        assert size(chunk) <= PARAGRAPH_LIMIT_BYTES
    assert [row for chunk in chunks for row in chunk.split("\n")[2:]] == original_rows
    assert result.paragraphs_split == 1 and result.tables_split == 1


def test_overlong_table_row_stays_whole_and_is_counted():
    long_row = "| 1 | " + "Zelle " * 200 + "|"
    original = "\n".join(["| Nr | Text |", "|---|---|", "| 0 | kurz |", long_row, "| 2 | kurz |"])
    result = split_long_paragraphs(original)
    chunks = paragraphs_of(result.text)
    assert any(long_row in chunk.split("\n") for chunk in chunks)
    assert result.paragraphs_over_limit == 1
    assert [row for chunk in chunks for row in chunk.split("\n")[2:]] == original.split("\n")[2:]


def test_unbreakable_word_stays_whole_and_is_counted():
    word = "x" * 1000
    result = split_long_paragraphs(f"Vor dem Wort steht Text. {word} und danach steht Text.")
    assert word in result.text.split()
    assert result.paragraphs_over_limit == 1


def test_counts_cover_prose_and_tables_separately():
    book = "\n\n".join([prose(40), "Kurz.", table(60), prose(30)])
    result = split_long_paragraphs(book)
    assert result.paragraphs_split == 3
    assert result.tables_split == 1
    assert result.paragraphs_over_limit == 0
