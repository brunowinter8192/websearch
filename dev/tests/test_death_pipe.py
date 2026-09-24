import os
import subprocess
import sys
import time

import psutil
import pytest

import src.death_pipe as death_pipe


def _spawn_dummy() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def _wait_until_gone(dummy: subprocess.Popen, timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if dummy.poll() is not None:
            return True
        time.sleep(0.05)
    return False


def test_spawn_watchdog_returns_none_when_nothing_to_protect():
    assert death_pipe.spawn_watchdog([], cleanup_dir=None) is None


def test_watchdog_kills_dummy_process_once_write_end_closes(tmp_path):
    dummy = _spawn_dummy()
    write_fd = death_pipe.spawn_watchdog([dummy.pid])
    assert write_fd is not None
    assert psutil.pid_exists(dummy.pid)

    os.close(write_fd)

    assert _wait_until_gone(dummy), "watchdog did not kill the dummy process in time"


def test_watchdog_removes_cleanup_dir_once_write_end_closes(tmp_path):
    protected_dir = tmp_path / "throwaway-profile"
    protected_dir.mkdir()
    dummy = _spawn_dummy()

    write_fd = death_pipe.spawn_watchdog([dummy.pid], cleanup_dir=str(protected_dir))
    os.close(write_fd)

    assert _wait_until_gone(dummy)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and protected_dir.exists():
        time.sleep(0.05)
    assert not protected_dir.exists()

    dummy.wait(timeout=5)


def test_watchdog_is_silent_noop_when_target_already_dead(tmp_path):
    dummy = _spawn_dummy()
    write_fd = death_pipe.spawn_watchdog([dummy.pid])

    dummy.kill()
    dummy.wait(timeout=5)

    log_path = tmp_path / "cli.log"
    os.environ["WEBSEARCH_DEATH_PIPE_LOG_PATH"] = str(log_path)
    try:
        os.close(write_fd)
        time.sleep(0.5)
        assert not log_path.exists(), "watchdog logged an intervention on the happy (already-dead) path"
    finally:
        del os.environ["WEBSEARCH_DEATH_PIPE_LOG_PATH"]


def test_watchdog_logs_intervention_when_it_actually_kills_something(tmp_path):
    dummy = _spawn_dummy()
    log_path = tmp_path / "cli.log"
    os.environ["WEBSEARCH_DEATH_PIPE_LOG_PATH"] = str(log_path)
    try:
        write_fd = death_pipe.spawn_watchdog([dummy.pid])
        os.close(write_fd)
        assert _wait_until_gone(dummy)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not log_path.exists():
            time.sleep(0.05)
        assert log_path.exists()
        assert "killed pids=" in log_path.read_text()
    finally:
        del os.environ["WEBSEARCH_DEATH_PIPE_LOG_PATH"]


def test_terminate_then_kill_returns_pids_that_died_gracefully(monkeypatch):
    class FakeProc:
        def __init__(self, pid):
            self.pid = pid
        def terminate(self):
            pass

    monkeypatch.setattr(death_pipe.psutil, "Process", FakeProc)
    monkeypatch.setattr(death_pipe.psutil, "wait_procs", lambda procs, timeout: (procs, []))
    result = death_pipe._terminate_then_kill([11, 22])
    assert sorted(result) == [11, 22]


def test_terminate_then_kill_force_kills_survivors(monkeypatch):
    killed = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid
        def terminate(self):
            pass
        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(death_pipe.psutil, "Process", FakeProc)
    monkeypatch.setattr(death_pipe.psutil, "wait_procs", lambda procs, timeout: ([], procs))
    result = death_pipe._terminate_then_kill([33])
    assert killed == [33]
    assert result == [33]


def test_terminate_then_kill_skips_already_dead_pid(monkeypatch):
    def raise_no_such_process(pid):
        raise death_pipe.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(death_pipe.psutil, "Process", raise_no_such_process)
    waited = []
    monkeypatch.setattr(death_pipe.psutil, "wait_procs", lambda procs, timeout: waited.append(procs) or ([], []))
    result = death_pipe._terminate_then_kill([404])
    assert waited == [[]]
    assert result == []
