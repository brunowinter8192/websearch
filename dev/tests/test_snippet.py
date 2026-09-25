# INFRASTRUCTURE
import pytest

from dev.search_pipeline._lib.text import strip_bloat
from src.config import MAX_SNIPPET_LEN
from src.search.snippet import truncate


# FUNCTIONS

def test_truncate_leaves_short_text_untouched():
    short = "This is a short snippet under 200 chars."
    assert truncate(short, MAX_SNIPPET_LEN) == short


def test_truncate_cuts_at_sentence_period_without_ellipsis():
    result = truncate("A" * 449 + ". " + "B" * 100, MAX_SNIPPET_LEN)
    assert result.endswith(".")
    assert "…" not in result
    assert len(result) == 450


def test_truncate_without_period_cuts_at_word_and_appends_ellipsis():
    result = truncate("word " * 120, MAX_SNIPPET_LEN)
    assert result.endswith("…")
    assert len(result) <= MAX_SNIPPET_LEN


def test_truncate_without_spaces_hard_cuts_and_appends_ellipsis():
    result = truncate("x" * 1000, MAX_SNIPPET_LEN)
    assert result.endswith("…")
    assert len(result) == MAX_SNIPPET_LEN + 1


@pytest.mark.parametrize("raw, expected", [
    ("data.Read moreWhat is attention?", "data."),
    ("not possible.Read more5,0(5) info", "not possible."),
    ("text.Read moreWriting about X", "text."),
    ("foo Read more about X", "foo"),
    ("· Translate this pageWir vergleichen git rebase und merge", "Wir vergleichen git rebase und merge"),
    ("  · Translate this pageSome foreign text here", "Some foreign text here"),
], ids=["p1a", "p1b", "p1c", "p1d", "p2a", "p2b"])
def test_dev_lib_strip_bloat_removes_read_more_and_translate_bloat(raw, expected):
    assert strip_bloat(raw) == expected
