import pytest

from src.search import search_web


def test_none_selects_the_default_engines():
    assert set(search_web._select_engines(None)) == set(search_web._DEFAULT_ENGINES)


def test_named_engines_are_selected_case_insensitively():
    assert set(search_web._select_engines("Google, brave")) == {"google", "brave"}


def test_unknown_engine_name_raises():
    with pytest.raises(ValueError, match="unknown engine.*nope"):
        search_web._select_engines("google,nope")
