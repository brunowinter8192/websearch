import shutil
from pathlib import Path

import pytest

import src.search.browser as browser
from dev.tests._browser_fakes import FakeChrome, _reset_state


async def _fake_resolve_bundle():
    return Path("/fake/chromium-1228/Google Chrome for Testing.app")


class FakeProcessManager:
    def __init__(self, process_creator=None):
        self.process_creator = process_creator
        self.start_calls = []

    def start_browser_process(self, binary_location, port, arguments):
        self.start_calls.append((binary_location, port, arguments))


def _patch_launch_mechanics(monkeypatch, resolve_bundle=_fake_resolve_bundle, acquire=None):
    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", resolve_bundle)
    monkeypatch.setattr(browser.browser_lock, "acquire", acquire or (lambda *a, **kw: "fake-lock-handle"))
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    monkeypatch.setattr(browser, "Chrome", lambda options: FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 12345)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")
    monkeypatch.setattr(browser, "_record_own_pids", lambda session_dir: None)
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda *a, **kw: None)
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: None)


@pytest.mark.asyncio
async def test_get_tab_orders_lock_reap_launch_anchor_record(monkeypatch):
    _reset_state(monkeypatch, browser)
    order = []

    async def fake_resolve_bundle():
        order.append("resolve_bundle")
        return Path("/fake/chromium-1228/Google Chrome for Testing.app")

    def fake_acquire(lock_path, hard_budget_s, on_stale=None):
        order.append("lock")
        return "fake-lock-handle"

    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", fake_resolve_bundle)
    monkeypatch.setattr(browser.browser_lock, "acquire", fake_acquire)
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: order.append("reap"))
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: order.append("anchor") or 42)
    monkeypatch.setattr(browser, "Chrome", lambda options: order.append("launch") or FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 54321)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")
    monkeypatch.setattr(browser, "_record_own_pids", lambda session_dir: order.append("record"))
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda *a, **kw: order.append("watchdog"))
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: order.append(("focus_watchdog", anchor_pid)))

    try:
        await browser.get_tab()

        assert order == ["resolve_bundle", "lock", "reap", "anchor", "launch", "record", "watchdog", ("focus_watchdog", 42)]
        assert browser._lock_handle == "fake-lock-handle"
        assert browser._browser.setup_user_dir_called is True
        assert browser._browser._connection_port == 54321
        assert browser._browser._connection_handler == "fake-conn-54321"
    finally:
        if browser._session_dir is not None:
            shutil.rmtree(browser._session_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_tab_self_launches_with_port_zero_and_forwards_arguments(monkeypatch):
    _reset_state(monkeypatch, browser)
    _patch_launch_mechanics(monkeypatch)

    try:
        await browser.get_tab()

        manager = browser._browser._browser_process_manager
        assert len(manager.start_calls) == 1
        binary_location, port, arguments = manager.start_calls[0]
        assert binary_location == "/fake/Google Chrome"
        assert port == 0
        assert "--no-startup-window" in arguments
        assert f"--user-data-dir={browser._session_dir}" in arguments
        assert Path(browser._session_dir).name.startswith(browser.SESSION_DIR_PREFIX)
        assert manager.process_creator.func is browser._open_background_process_creator
        assert manager.process_creator.args == (Path("/fake/chromium-1228/Google Chrome for Testing.app"),)
    finally:
        if browser._session_dir is not None:
            shutil.rmtree(browser._session_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: "fake-lock-handle")
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    monkeypatch.setattr(browser, "Chrome", lambda options: FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 54321)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")

    def _fake_record_own_pids(session_dir):
        monkeypatch.setattr(browser, "_owned_pids", [111, 222])

    monkeypatch.setattr(browser, "_record_own_pids", _fake_record_own_pids)

    calls = []
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda pids, cleanup_dir=None: calls.append((pids, cleanup_dir)))
    focus_calls = []
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: focus_calls.append((pids, anchor_pid)))

    try:
        await browser.get_tab()

        assert calls == [([111, 222], browser._session_dir)]
        assert focus_calls == [([111, 222], 999)]
    finally:
        if browser._session_dir is not None:
            shutil.rmtree(browser._session_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_tab_reuses_existing_browser_without_relocking(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))
    called = []
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: called.append(1))
    await browser.get_tab()
    assert called == []


@pytest.mark.asyncio
async def test_get_tab_uses_a_fresh_directory_each_run(monkeypatch):
    _reset_state(monkeypatch, browser)
    _patch_launch_mechanics(monkeypatch)

    await browser.get_tab()
    first_dir = browser._session_dir

    monkeypatch.setattr(browser, "_browser", None)
    monkeypatch.setattr(browser, "_session_dir", None)
    await browser.get_tab()
    second_dir = browser._session_dir

    try:
        assert first_dir != second_dir
        assert Path(first_dir).name.startswith(browser.SESSION_DIR_PREFIX)
        assert Path(second_dir).name.startswith(browser.SESSION_DIR_PREFIX)
    finally:
        shutil.rmtree(first_dir, ignore_errors=True)
        shutil.rmtree(second_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_tab_uses_the_same_lock_path_across_runs(monkeypatch):
    _reset_state(monkeypatch, browser)
    lock_paths = []

    def fake_acquire(lock_path, hard_budget_s, on_stale=None):
        lock_paths.append(lock_path)
        return "fake-lock-handle"

    _patch_launch_mechanics(monkeypatch, acquire=fake_acquire)

    await browser.get_tab()
    first_dir = browser._session_dir
    monkeypatch.setattr(browser, "_browser", None)
    monkeypatch.setattr(browser, "_session_dir", None)
    await browser.get_tab()
    second_dir = browser._session_dir

    try:
        assert len(lock_paths) == 2
        assert lock_paths[0] == lock_paths[1] == browser.LOCK_PATH
    finally:
        shutil.rmtree(first_dir, ignore_errors=True)
        shutil.rmtree(second_dir, ignore_errors=True)


def test_lock_path_is_fixed_and_not_derived_from_any_per_run_value():
    assert browser.LOCK_PATH == Path.home() / ".websearch" / "browser-session.lock"


@pytest.mark.asyncio
async def test_get_tab_removes_its_own_partial_directory_on_launch_failure(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    released = []

    class FakeLockHandle:
        def release(self):
            released.append(1)

    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: FakeLockHandle())
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    captured_dir = []

    def raising_chrome(options):
        captured_dir.append(browser._session_dir)
        raise RuntimeError("launch failed")

    monkeypatch.setattr(browser, "Chrome", raising_chrome)

    with pytest.raises(RuntimeError):
        await browser.get_tab()

    assert captured_dir and captured_dir[0] is not None
    assert not Path(captured_dir[0]).exists()
    assert browser._session_dir is None
    assert released == [1]
