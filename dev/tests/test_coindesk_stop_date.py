from datetime import datetime, timedelta, timezone

import pytest

from src.news.platforms.coindesk.config import DEFAULT_DELTA_DAYS, FULL_MODE_FLOOR
from src.news.platforms.coindesk.discover import _parse_stop_date


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def test_parse_stop_date_full_returns_floor():
    assert _parse_stop_date("full") == FULL_MODE_FLOOR


def test_parse_stop_date_delta_is_the_default_window():
    assert _parse_stop_date("delta") == _days_ago(DEFAULT_DELTA_DAYS)


def test_parse_stop_date_integer_is_that_many_days():
    assert _parse_stop_date("7") == _days_ago(7)


def test_parse_stop_date_unparseable_value_raises():
    with pytest.raises(ValueError):
        _parse_stop_date("deltaa")
