# INFRASTRUCTURE
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.log_janitor import get_retention_days, maybe_prune_jsonl, maybe_prune_sidecars


# FUNCTIONS

@pytest.fixture
def retention_14(monkeypatch):
    monkeypatch.setenv("WEBSEARCH_LOG_RETENTION_DAYS", "14")


def test_get_retention_days_defaults_to_90_when_unset(monkeypatch):
    monkeypatch.delenv("WEBSEARCH_LOG_RETENTION_DAYS", raising=False)
    assert get_retention_days() == 90


def test_get_retention_days_raises_on_non_integer_value(monkeypatch):
    monkeypatch.setenv("WEBSEARCH_LOG_RETENTION_DAYS", "not-a-number")
    with pytest.raises(ValueError):
        get_retention_days()


def test_prune_jsonl_drops_lines_older_than_retention_and_touches_marker(tmp_path, retention_14):
    log = tmp_path / "query_log.jsonl"
    _write_jsonl(log)
    maybe_prune_jsonl(log)
    assert _queries(log) == ["recent-1", "recent-2", "recent-3"]
    assert Path(str(log) + ".lastprune").exists()


def test_prune_sidecars_deletes_old_files_and_touches_marker(tmp_path, retention_14):
    sidecar_dir = tmp_path / "scrape_content"
    _write_sidecars(sidecar_dir)
    maybe_prune_sidecars(sidecar_dir)
    assert [p.name for p in sidecar_dir.glob("*.md")] == ["recent.md"]
    assert (sidecar_dir / ".lastprune").exists()


def test_prune_jsonl_skips_when_marker_is_recent(tmp_path, retention_14):
    log = tmp_path / "query_log.jsonl"
    _write_jsonl(log)
    maybe_prune_jsonl(log)
    injected = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": injected, "query": "injected-old"}) + "\n")
    maybe_prune_jsonl(log)
    assert "injected-old" in _queries(log)


def test_prune_jsonl_reruns_when_marker_is_stale(tmp_path, retention_14):
    log = tmp_path / "query_log.jsonl"
    _write_jsonl(log)
    maybe_prune_jsonl(log)
    injected = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": injected, "query": "injected-old"}) + "\n")
    stale = time.time() - 3700
    os.utime(Path(str(log) + ".lastprune"), (stale, stale))
    maybe_prune_jsonl(log)
    assert "injected-old" not in _queries(log)
    assert len(_queries(log)) == 3


def test_prune_jsonl_keeps_unparseable_lines(tmp_path, retention_14, caplog):
    import logging
    log = tmp_path / "query_log.jsonl"
    _write_jsonl(log)
    with open(log, "a", encoding="utf-8") as f:
        f.write("not json at all\n")
        f.write(json.dumps({"no_ts": 1}) + "\n")
    with caplog.at_level(logging.WARNING, logger="src.log_janitor"):
        maybe_prune_jsonl(log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert "not json at all" in lines
    assert json.dumps({"no_ts": 1}) in lines
    assert [json.loads(l).get("query") for l in lines if l.startswith("{")][:3] == ["recent-1", "recent-2", "recent-3"]
    assert len([m for m in caplog.messages if "keeping unparseable" in m]) == 2


def _write_jsonl(path):
    now = datetime.now(timezone.utc)
    entries = [
        {"ts": (now - timedelta(days=20)).isoformat(), "query": "old-1"},
        {"ts": (now - timedelta(days=20)).isoformat(), "query": "old-2"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-1"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-2"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-3"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _queries(path):
    return [json.loads(line)["query"] for line in path.read_text(encoding="utf-8").splitlines()]


def _write_sidecars(sidecar_dir):
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    old_mtime = time.time() - 20 * 86400
    for name in ("old-a.md", "old-b.md"):
        f = sidecar_dir / name
        f.write_text(f"<!-- {name} -->", encoding="utf-8")
        os.utime(f, (old_mtime, old_mtime))
    (sidecar_dir / "recent.md").write_text("<!-- recent -->", encoding="utf-8")
