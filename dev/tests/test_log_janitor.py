import pytest

from src.log_janitor import get_retention_days


def test_get_retention_days_defaults_to_90_when_unset(monkeypatch):
    monkeypatch.delenv("WEBSEARCH_LOG_RETENTION_DAYS", raising=False)
    assert get_retention_days() == 90


def test_get_retention_days_raises_on_non_integer_value(monkeypatch):
    """2026-09-09: the silent fallback to 14 on an unparsable value was removed — no supporting
    observation (the env var is set nowhere in the repo: cli.py, skills, configs). A malformed
    value now raises at first use instead of silently running with the default."""
    monkeypatch.setenv("WEBSEARCH_LOG_RETENTION_DAYS", "not-a-number")
    with pytest.raises(ValueError):
        get_retention_days()
