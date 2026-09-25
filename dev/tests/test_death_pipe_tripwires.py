# INFRASTRUCTURE
import shutil

import pytest

import src.death_pipe as death_pipe

_REAL_RMTREE = shutil.rmtree


# FUNCTIONS

def test_intervention_write_failure_raises(tmp_path, monkeypatch):
    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file")
    monkeypatch.setattr(death_pipe, "_LOG_PATH", blocker / "nested" / "cli.log")
    with pytest.raises(OSError):
        death_pipe._log_intervention("x")


def test_intervention_line_is_appended(tmp_path, monkeypatch):
    log = tmp_path / "logs" / "cli.log"
    monkeypatch.setattr(death_pipe, "_LOG_PATH", log)
    death_pipe._log_intervention("killed pids=[1]")
    assert "killed pids=[1]" in log.read_text()


def test_dir_removed_reported_true_when_it_is_gone(monkeypatch, tmp_path):
    target = tmp_path / "profile"
    target.mkdir()
    logged = _run_main(monkeypatch, tmp_path, "", target, lambda p, ignore_errors: _REAL_RMTREE(p))
    assert len(logged) == 1 and f"removed_dir={target}" in logged[0]


def test_dir_removed_not_claimed_when_removal_failed(monkeypatch, tmp_path):
    target = tmp_path / "profile"
    target.mkdir()
    logged = _run_main(monkeypatch, tmp_path, "", target, lambda p, ignore_errors: None)
    assert logged == []


def _run_main(monkeypatch, tmp_path, pids_arg, cleanup_dir, rmtree):
    logged = []
    monkeypatch.setattr(death_pipe.sys, "argv", ["death_pipe.py", pids_arg, str(cleanup_dir)])
    monkeypatch.setattr(death_pipe.os, "read", lambda fd, n: b"")
    monkeypatch.setattr(death_pipe, "terminate_then_kill", lambda pids: [])
    monkeypatch.setattr(death_pipe.shutil, "rmtree", rmtree)
    monkeypatch.setattr(death_pipe, "_log_intervention", logged.append)
    death_pipe._watchdog_main()
    return logged
