# INFRASTRUCTURE
from datetime import datetime, timedelta, timezone

import pytest

from src.news.platforms.coindesk.config import DEFAULT_DELTA_DAYS, FULL_MODE_FLOOR
from src.news.platforms.coindesk import discover
from src.news.platforms.coindesk.discover import _parse_stop_date

FROZEN_NOW = datetime(2026, 9, 24, 23, 59, 59, tzinfo=timezone.utc)


# FUNCTIONS

@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch):
    monkeypatch.setattr(discover, "datetime", _FrozenDatetime)


def test_parse_stop_date_full_returns_floor():
    assert _parse_stop_date("full") == FULL_MODE_FLOOR


def test_parse_stop_date_delta_is_the_default_window():
    assert _parse_stop_date("delta") == _days_ago(DEFAULT_DELTA_DAYS)


def test_parse_stop_date_integer_is_that_many_days():
    assert _parse_stop_date("7") == _days_ago(7)


def test_parse_stop_date_unparseable_value_raises():
    with pytest.raises(ValueError):
        _parse_stop_date("deltaa")


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


def _days_ago(n: int) -> str:
    return (FROZEN_NOW.date() - timedelta(days=n)).isoformat()
