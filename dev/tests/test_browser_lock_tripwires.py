# INFRASTRUCTURE
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import pytest

import src.search.browser_lock as browser_lock


# FUNCTIONS

def test_stale_takeover_logs_pid_and_age_before_breaking(tmp_path, caplog):
    lock_path = tmp_path / "session.lock"
    sidecar = lock_path.with_suffix(".json")
    stuck = browser_lock.acquire(lock_path, hard_budget_s=9999.0)
    sidecar.write_text(json.dumps({"pid": 4242, "started_at": _old_started_at(120)}))
    with caplog.at_level(logging.WARNING, logger="src.search.browser_lock"):
        handle = browser_lock.acquire(lock_path, hard_budget_s=1.0)
    handle.release()
    stuck._fd.close()
    messages = [m for m in caplog.messages if "breaking stale" in m]
    assert len(messages) == 1
    assert "pid=4242" in messages[0] and "age=" in messages[0]


@pytest.mark.parametrize("content", ["not json{", json.dumps({"pid": 1}), json.dumps({"started_at": "garbage"})])
def test_unreadable_sidecar_raises(tmp_path, content):
    sidecar = tmp_path / "s.json"
    sidecar.write_text(content)
    with pytest.raises((json.JSONDecodeError, KeyError, ValueError)):
        browser_lock._sidecar_age_s(sidecar)


def test_missing_sidecar_is_not_stale(tmp_path):
    assert browser_lock._sidecar_age_s(tmp_path / "absent.json") is None


def test_sidecar_is_written_atomically_without_leftover_tmp(tmp_path):
    lock_path = tmp_path / "session.lock"
    handle = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["session.json", "session.lock"]
    assert json.loads(lock_path.with_suffix(".json").read_text())["pid"] == os.getpid()
    handle.release()


def _old_started_at(seconds):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
