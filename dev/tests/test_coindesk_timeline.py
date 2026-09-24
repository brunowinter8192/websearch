import json

import pytest

from src.news.platforms.coindesk.timeline import parse_articles


def test_parse_articles_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_articles(b"not json")


def test_parse_articles_returns_empty_list_for_real_bottom_shape():
    assert parse_articles(b'{"foo": 1}') == []
