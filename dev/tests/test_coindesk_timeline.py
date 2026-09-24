import json

import pytest

from src.news.platforms.coindesk.timeline import parse_articles


def test_parse_articles_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_articles(b"not json")


def test_parse_articles_returns_empty_list_for_real_bottom_shape():
    assert parse_articles(b'{"foo": 1}') == []


def _article(**over):
    base = {"_id": "abc", "pathname": "/markets/2026/09/24/x/", "storyType": "news", "title": "T",
            "articleDates": {"displayDate": "2026-09-24T10:00:00Z"}}
    base.update(over)
    return base


def test_parse_articles_reads_the_observed_shape():
    body = json.dumps([_article()]).encode()
    assert parse_articles(body) == [{
        "_id": "abc", "storyType": "news", "pathname": "/markets/2026/09/24/x/",
        "displayDate": "2026-09-24T10:00:00Z", "title": "T",
    }]


def test_parse_articles_reads_list_nested_under_a_dict_key():
    body = json.dumps({"articles": [_article()]}).encode()
    assert parse_articles(body)[0]["_id"] == "abc"


@pytest.mark.parametrize("field", ["_id", "pathname", "articleDates"])
def test_parse_articles_missing_required_field_raises(field):
    art = _article()
    del art[field]
    with pytest.raises(KeyError):
        parse_articles(json.dumps([art]).encode())


def test_parse_articles_does_not_accept_alternative_date_keys():
    art = _article()
    del art["articleDates"]
    art["displayDate"] = "2026-09-24"
    with pytest.raises(KeyError):
        parse_articles(json.dumps([art]).encode())
