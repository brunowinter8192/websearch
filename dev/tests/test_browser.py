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


class FakeChrome:
    def __init__(self, options):
        self.options = options
        self.started = False

    async def start(self):
        self.started = True
        return "fake-tab"

    async def stop(self):
        pass


class FakeCompletedProcess:
    def __init__(self, stdout):
        self.stdout = stdout


def _reset_state(monkeypatch):
    monkeypatch.setattr(browser, "_browser", None)
    monkeypatch.setattr(browser, "_tab", None)
    monkeypatch.setattr(browser, "_lock_handle", None)
    monkeypatch.setattr(browser, "_owned_pids", [])
    monkeypatch.setattr(browser, "_focus_watchdog_task", None)


# _reap_session_profile / _record_own_pids: pgrep output parsing + kill dispatch

def test_reap_session_profile_kills_parsed_pids(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("111\n222\n"))
    killed = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: killed.append(pids))
    browser._reap_session_profile()
    assert killed == [[111, 222]]


def test_reap_session_profile_no_survivors_is_noop(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess(""))
    killed = []
    monkeypatch.setattr(browser, "_terminate_then_kill", lambda pids, timeout_s=5.0: killed.append(pids))
    browser._reap_session_profile()
    assert killed == []


def test_record_own_pids_sets_module_state(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("333\n444\n"))
    browser._record_own_pids()
    assert browser._owned_pids == [333, 444]


# _terminate_then_kill: terminate every resolvable pid, kill only what's still alive after wait_procs

def test_terminate_then_kill_terminates_and_waits(monkeypatch):
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)

    def raise_no_such_process(pid):
        raise browser.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(browser.psutil, "Process", raise_no_such_process)
    waited = []
    monkeypatch.setattr(browser.psutil, "wait_procs", lambda procs, timeout: waited.append(procs) or ([], []))
    browser._terminate_then_kill([404], timeout_s=1.0)
    assert waited == [[]]


# get_tab: critical-section ordering — lock acquired, then reap, then launch, then own-pids recorded

@pytest.mark.asyncio
async def test_get_tab_orders_lock_reap_launch_anchor_record(monkeypatch):
    _reset_state(monkeypatch)
    order = []

    def fake_acquire(lock_path, hard_budget_s, on_stale=None):
        order.append("lock")
        return "fake-lock-handle"

    monkeypatch.setattr(browser.browser_lock, "acquire", fake_acquire)
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: order.append("reap"))
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: order.append("anchor") or 42)
    monkeypatch.setattr(browser, "Chrome", lambda options: order.append("launch") or FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", lambda process_creator: None)
    monkeypatch.setattr(browser, "_record_own_pids", lambda: order.append("record"))
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda *a, **kw: order.append("watchdog"))
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: order.append(("focus_watchdog", anchor_pid)))

    tab = await browser.get_tab()

    assert order == ["lock", "reap", "anchor", "launch", "record", "watchdog", ("focus_watchdog", 42)]
    assert tab == "fake-tab"
    assert browser._lock_handle == "fake-lock-handle"


@pytest.mark.asyncio
async def test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: "fake-lock-handle")
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    monkeypatch.setattr(browser, "Chrome", lambda options: FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", lambda process_creator: None)
    def _fake_record_own_pids():
        monkeypatch.setattr(browser, "_owned_pids", [111, 222])

    monkeypatch.setattr(browser, "_record_own_pids", _fake_record_own_pids)

    calls = []
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda pids, cleanup_dir=None: calls.append((pids, cleanup_dir)))
    focus_calls = []
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: focus_calls.append((pids, anchor_pid)))

    await browser.get_tab()

    assert calls == [([111, 222], None)]
    assert focus_calls == [([111, 222], 999)]


@pytest.mark.asyncio
async def test_get_tab_reuses_existing_browser_without_relocking(monkeypatch):
    _reset_state(monkeypatch)
    fake_tab = object()
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))
    monkeypatch.setattr(browser, "_tab", fake_tab)
    called = []
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: called.append(1))
    result = await browser.get_tab()
    assert result is fake_tab
    assert called == []


# _get_frontmost_pid / _activate_pid: osascript stdout parsing + pid embedded in the AppleScript call

def test_get_frontmost_pid_parses_stdout(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess("54620\n"))
    assert browser._get_frontmost_pid() == 54620


def test_get_frontmost_pid_returns_none_on_unparseable_stdout(monkeypatch):
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: FakeCompletedProcess(""))
    assert browser._get_frontmost_pid() is None


def test_activate_pid_embeds_pid_in_applescript_command(monkeypatch):
    _reset_state(monkeypatch)
    commands = []
    monkeypatch.setattr(browser.subprocess, "run", lambda cmd, **kw: commands.append(cmd) or FakeCompletedProcess(""))
    browser._activate_pid(1344)
    assert any("unix id is 1344" in arg for arg in commands[0])


# _focus_steal_watchdog_by_pid: reclaims focus only for OWNED pids, never for a same-named
# non-owned process (e.g. the user's own separate "Google Chrome") — the hazard this milestone
# exists to avoid, since both processes share the same frontmost APP NAME and are only
# distinguishable by pid. The known-good "last_other_pid" anchor is captured by the CALLER
# (get_tab(), before Chrome ever launches) and passed in, not re-derived by the watchdog's own
# first read — a live-verified bug (2026-09-15 probe run) showed the watchdog's own post-launch
# self-capture can be poisoned by an owned pid already being frontmost from Chrome's own launch,
# permanently disabling reclaim until Chrome happened to cede focus on its own.

@pytest.mark.asyncio
async def test_focus_steal_watchdog_by_pid_ignores_non_owned_frontmost_pid(monkeypatch):
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))

    await browser.close_browser()

    assert browser._focus_watchdog_task is None
    assert browser._browser is None


# kill_own_chrome: graceful close -> PID safety net -> lock release, no-op when nothing was touched

@pytest.mark.asyncio
async def test_kill_own_chrome_noop_when_browser_never_started(monkeypatch):
    _reset_state(monkeypatch)
    close_called = []
    monkeypatch.setattr(browser, "close_browser", _make_async_recorder(close_called))
    await browser.kill_own_chrome()
    assert close_called == []


@pytest.mark.asyncio
async def test_kill_own_chrome_full_teardown_sequence(monkeypatch):
    _reset_state(monkeypatch)
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
    _reset_state(monkeypatch)
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
