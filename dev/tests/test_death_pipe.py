# INFRASTRUCTURE
import os
import subprocess
import sys
import time

import psutil
import pytest

import src.death_pipe as death_pipe


# FUNCTIONS

def test_spawn_watchdog_returns_none_when_nothing_to_protect():
    assert death_pipe.spawn_watchdog([], cleanup_dir=None) is None


def test_watchdog_kills_dummy_process_once_write_end_closes(dummy_process, watchdog_log_path):
    write_fd = death_pipe.spawn_watchdog([dummy_process.pid])
    assert write_fd is not None
    assert psutil.pid_exists(dummy_process.pid)

    os.close(write_fd)

    assert _wait_until(lambda: dummy_process.poll() is not None), "watchdog did not kill the dummy process in time"


def test_watchdog_removes_cleanup_dir_once_write_end_closes(tmp_path, dummy_process, watchdog_log_path):
    protected_dir = tmp_path / "throwaway-profile"
    protected_dir.mkdir()

    write_fd = death_pipe.spawn_watchdog([dummy_process.pid], cleanup_dir=str(protected_dir))
    os.close(write_fd)

    assert _wait_until(lambda: dummy_process.poll() is not None)
    assert _wait_until(lambda: not protected_dir.exists())


def test_watchdog_is_silent_noop_when_target_already_dead(dummy_process, watchdog_log_path):
    write_fd = death_pipe.spawn_watchdog([dummy_process.pid])
    watchdog = _find_watchdog(dummy_process.pid)

    dummy_process.kill()
    dummy_process.wait(timeout=5)

    os.close(write_fd)
    assert _wait_until(lambda: _has_exited(watchdog)), "watchdog did not exit"
    assert not watchdog_log_path.exists(), "watchdog logged an intervention on the happy (already-dead) path"


def test_watchdog_logs_intervention_when_it_actually_kills_something(dummy_process, watchdog_log_path):
    write_fd = death_pipe.spawn_watchdog([dummy_process.pid])
    os.close(write_fd)
    assert _wait_until(lambda: dummy_process.poll() is not None)
    assert _wait_until(watchdog_log_path.exists)
    assert "killed pids=" in watchdog_log_path.read_text()


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


@pytest.fixture
def dummy_process():
    dummy = _spawn_dummy()
    yield dummy
    if dummy.poll() is None:
        dummy.kill()
    dummy.wait(timeout=5)


def _wait_until(predicate, timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _find_watchdog(target_pid: int) -> psutil.Process:
    for proc in psutil.process_iter(["cmdline"]):
        cmdline = proc.info["cmdline"] or []
        if any(part.endswith("death_pipe.py") for part in cmdline) and str(target_pid) in cmdline:
            return proc
    raise AssertionError("watchdog process not found")


def _has_exited(proc: psutil.Process) -> bool:
    try:
        return proc.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


@pytest.fixture
def watchdog_log_path(tmp_path, monkeypatch):
    log_path = tmp_path / "cli.log"
    monkeypatch.setenv("WEBSEARCH_DEATH_PIPE_LOG_PATH", str(log_path))
    return log_path


def _spawn_dummy() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
