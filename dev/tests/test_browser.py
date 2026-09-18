"""Tests for browser.py's own-run-scoped Chrome lifecycle: PID snapshot/kill mechanics
(_reap_session_profile/_record_own_pids/_terminate_then_kill) with subprocess+psutil mocked at the
I/O boundary, get_tab()'s critical-section ordering (cross-process lock -> reap -> launch ->
record-own-pids -> death_pipe watchdog -> PID-keyed focus watchdog), close_browser()'s watchdog
cancellation, and kill_own_chrome()'s teardown (graceful close_browser -> PID-scoped safety-net
kill -> lock release), including the no-op path for a run that never touched the browser.

No real Chrome/flock involved here (browser_lock's own real-flock behavior is covered by
test_browser_lock.py) — pydoll's Chrome and psutil/subprocess are faked per test, module globals
reset via monkeypatch so tests don't leak state into each other.
"""
import asyncio

import pytest

import src.search.browser as browser
from dev.tests._browser_fakes import FakeChrome, _reset_state


class FakeCompletedProcess:
    def __init__(self, stdout):
        self.stdout = stdout


def test_find_app_bundle_walks_up_to_app_suffix():
    bundle = browser._find_app_bundle(
        "/Users/x/Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
    assert str(bundle).endswith("Google Chrome for Testing.app")


def test_find_app_bundle_returns_none_when_no_app_ancestor():
    assert browser._find_app_bundle("/usr/local/bin/chrome") is None


def test_open_background_process_creator_targets_resolved_bundle_path_not_bare_name(monkeypatch):
    _reset_state(monkeypatch, browser)
    captured = []
    monkeypatch.setattr(browser.subprocess, "Popen", lambda cmd, **kw: captured.append(cmd))
    bundle_path = browser.Path("/fake/chromium-1228/Google Chrome for Testing.app")
    browser._open_background_process_creator(bundle_path, ["/ignored-binary", "--user-data-dir=/x"])
    cmd = captured[0]
    assert cmd == ["open", "-g", "-n", "-a", str(bundle_path), "--args", "--user-data-dir=/x"]
    assert cmd[cmd.index("-a") + 1] != "Google Chrome"


# _reap_session_profile / _record_own_pids: pgrep output parsing + kill dispatch

def test_reap_session_profile_kills_parsed_pids(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("111\n222\n"))
    killed = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: killed.append(pids))
    browser._reap_session_profile()
    assert killed == [[111, 222]]


def test_reap_session_profile_no_survivors_is_noop(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess(""))
    killed = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: killed.append(pids))
    browser._reap_session_profile()
    assert killed == []


def test_record_own_pids_sets_module_state(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("333\n444\n"))
    browser._record_own_pids()
    assert browser._owned_pids == [333, 444]


# _terminate_then_kill: terminate every resolvable pid, kill only what's still alive after wait_procs

def test_terminate_then_kill_terminates_and_waits(monkeypatch):
    _reset_state(monkeypatch, browser)
    calls = {"terminated": [], "killed": [], "waited": None}

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def terminate(self):
            calls["terminated"].append(self.pid)

        def kill(self):
            calls["killed"].append(self.pid)

    monkeypatch.setattr(browser.psutil, "Process", FakeProc)

    def fake_wait_procs(procs, timeout):
        calls["waited"] = (list(procs), timeout)
        return procs, []  # everything exited gracefully

    monkeypatch.setattr(browser.psutil, "wait_procs", fake_wait_procs)
    browser._terminate_then_kill([1, 2], timeout_s=7.0)
    assert calls["terminated"] == [1, 2]
    assert calls["waited"][1] == 7.0
    assert calls["killed"] == []


def test_terminate_then_kill_force_kills_survivors(monkeypatch):
    _reset_state(monkeypatch, browser)
    calls = {"killed": []}

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def terminate(self):
            pass

        def kill(self):
            calls["killed"].append(self.pid)

    monkeypatch.setattr(browser.psutil, "Process", FakeProc)
    monkeypatch.setattr(browser.psutil, "wait_procs", lambda procs, timeout: ([], procs))
    browser._terminate_then_kill([9], timeout_s=1.0)
    assert calls["killed"] == [9]


def test_terminate_then_kill_skips_already_dead_pid(monkeypatch):
    _reset_state(monkeypatch, browser)

    def raise_no_such_process(pid):
        raise browser.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(browser.psutil, "Process", raise_no_such_process)
    waited = []
    monkeypatch.setattr(browser.psutil, "wait_procs", lambda procs, timeout: waited.append(procs) or ([], []))
    browser._terminate_then_kill([404], timeout_s=1.0)
    assert waited == [[]]


# _get_frontmost_pid / _activate_pid: osascript stdout parsing + pid embedded in the AppleScript call

def test_get_frontmost_pid_parses_stdout(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("54620\n"))
    assert browser._get_frontmost_pid() == 54620


def test_get_frontmost_pid_returns_none_on_unparseable_stdout(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess(""))
    assert browser._get_frontmost_pid() is None


def test_activate_pid_embeds_pid_in_applescript_command(monkeypatch):
    _reset_state(monkeypatch, browser)
    commands = []
    monkeypatch.setattr(browser.subprocess, "run", lambda cmd, **kw: commands.append(cmd) or FakeCompletedProcess(""))
    browser._activate_pid(1344)
    assert any("unix id is 1344" in arg for arg in commands[0])


# _focus_steal_watchdog_by_pid: reclaims only OWNED pids, using an externally-supplied anchor

@pytest.mark.asyncio
async def test_focus_steal_watchdog_by_pid_ignores_non_owned_frontmost_pid(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "FOCUS_STEAL_POLL_INTERVAL_S", 0)
    pid_sequence = iter([999, 999])

    def fake_get_pid():
        try:
            return next(pid_sequence)
        except StopIteration:
            raise asyncio.CancelledError

    monkeypatch.setattr(browser, "_get_frontmost_pid", fake_get_pid)
    activated = []
    monkeypatch.setattr(browser, "_activate_pid", lambda pid: activated.append(pid))

    with pytest.raises(asyncio.CancelledError):
        await browser._focus_steal_watchdog_by_pid({123}, 999)

    assert activated == []


@pytest.mark.asyncio
async def test_focus_steal_watchdog_by_pid_reclaims_on_owned_pid_steal(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "FOCUS_STEAL_POLL_INTERVAL_S", 0)
    pid_sequence = iter([999, 123])

    def fake_get_pid():
        try:
            return next(pid_sequence)
        except StopIteration:
            raise asyncio.CancelledError

    monkeypatch.setattr(browser, "_get_frontmost_pid", fake_get_pid)
    activated = []
    monkeypatch.setattr(browser, "_activate_pid", lambda pid: activated.append(pid))

    with pytest.raises(asyncio.CancelledError):
        await browser._focus_steal_watchdog_by_pid({123}, 999)

    assert activated == [999]


@pytest.mark.asyncio
async def test_focus_steal_watchdog_by_pid_reclaims_immediately_when_already_stolen_at_start(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "FOCUS_STEAL_POLL_INTERVAL_S", 0)
    pid_sequence = iter([123, 123])

    def fake_get_pid():
        try:
            return next(pid_sequence)
        except StopIteration:
            raise asyncio.CancelledError

    monkeypatch.setattr(browser, "_get_frontmost_pid", fake_get_pid)
    activated = []
    monkeypatch.setattr(browser, "_activate_pid", lambda pid: activated.append(pid))

    with pytest.raises(asyncio.CancelledError):
        await browser._focus_steal_watchdog_by_pid({123}, 999)

    assert activated == [999, 999]


@pytest.mark.asyncio
async def test_close_browser_cancels_live_focus_watchdog_before_stopping(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))

    async def never_ending():
        await asyncio.sleep(1000)

    task = asyncio.get_event_loop().create_task(never_ending())
    monkeypatch.setattr(browser, "_focus_watchdog_task", task)

    await browser.close_browser()

    assert task.cancelled()
    assert browser._focus_watchdog_task is None
    assert browser._browser is None


@pytest.mark.asyncio
async def test_close_browser_noop_watchdog_cancel_when_never_started(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))

    await browser.close_browser()

    assert browser._focus_watchdog_task is None
    assert browser._browser is None


# kill_own_chrome: graceful close -> PID safety net -> lock release, no-op when nothing was touched

@pytest.mark.asyncio
async def test_kill_own_chrome_noop_when_browser_never_started(monkeypatch):
    _reset_state(monkeypatch, browser)
    close_called = []
    monkeypatch.setattr(browser, "close_browser", _make_async_recorder(close_called))
    await browser.kill_own_chrome()
    assert close_called == []


@pytest.mark.asyncio
async def test_kill_own_chrome_full_teardown_sequence(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))
    monkeypatch.setattr(browser, "_owned_pids", [1, 2])

    close_called = []
    monkeypatch.setattr(browser, "close_browser", _make_async_recorder(close_called))
    kill_called = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: kill_called.append((pids, timeout_s)))

    released = []

    class FakeLockHandle:
        def release(self):
            released.append(1)

    monkeypatch.setattr(browser, "_lock_handle", FakeLockHandle())

    await browser.kill_own_chrome()

    assert close_called == [1]
    assert kill_called == [([1, 2], 10.0)]
    assert released == [1]
    assert browser._owned_pids == []
    assert browser._lock_handle is None


@pytest.mark.asyncio
async def test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))
    monkeypatch.setattr(browser, "_owned_pids", [7])

    async def raising_close_browser():
        raise ConnectionError("dead websocket")

    monkeypatch.setattr(browser, "close_browser", raising_close_browser)
    kill_called = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: kill_called.append((pids, timeout_s)))

    released = []

    class FakeLockHandle:
        def release(self):
            released.append(1)

    monkeypatch.setattr(browser, "_lock_handle", FakeLockHandle())

    await browser.kill_own_chrome()

    assert kill_called == [([7], 10.0)]
    assert released == [1]
    assert browser._browser is None
    assert browser._owned_pids == []
    assert browser._lock_handle is None


def _make_async_recorder(sink):
    async def recorder():
        sink.append(1)
    return recorder


def test_kill_own_chrome_atexit_runs_event_loop(monkeypatch):
    called = []

    async def fake_kill_own_chrome():
        called.append(1)

    monkeypatch.setattr(browser, "kill_own_chrome", fake_kill_own_chrome)
    browser.kill_own_chrome_atexit()
    assert called == [1]
