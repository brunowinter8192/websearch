import json

import pytest

from src.news.platforms.coindesk.timeline import parse_articles


def test_parse_articles_raises_on_invalid_json():
    """2026-09-09: the except Exception: return [] handler was removed — no supporting
    observation (no process-docs entry documents a real parse failure of the timeline API). A
    non-JSON body now raises instead of masquerading as an empty/exhausted page."""
    with pytest.raises(json.JSONDecodeError):
        parse_articles(b"not json")


def test_parse_articles_returns_empty_list_for_real_bottom_shape():
    """A valid JSON payload carrying no article list at all (the real API-bottom shape) still
    returns [] — now the ONLY outcome that means it, since a parse failure no longer collapses
    into the same result."""
    assert parse_articles(b'{"foo": 1}') == []
