import pytest

from src.log_janitor import get_retention_days


def test_get_retention_days_defaults_to_90_when_unset(monkeypatch):
    monkeypatch.delenv("WEBSEARCH_LOG_RETENTION_DAYS", raising=False)
    assert get_retention_days() == 90


def test_get_retention_days_raises_on_non_integer_value(monkeypatch):
    monkeypatch.setenv("WEBSEARCH_LOG_RETENTION_DAYS", "not-a-number")
    with pytest.raises(ValueError):
        get_retention_days()
