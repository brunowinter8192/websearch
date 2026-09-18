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


# get_tab: critical-section ordering — lock acquired, then reap, then self-launch (no .start(),
# no initial tab — see src/search/DOCS.md for why), then own-pids recorded once the devtools port
# confirms Chrome is actually up

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
    monkeypatch.setattr(browser, "_clear_stale_devtools_port", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: order.append("anchor") or 42)
    monkeypatch.setattr(browser, "Chrome", lambda options: order.append("launch") or FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 54321)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")
    monkeypatch.setattr(browser, "_record_own_pids", lambda: order.append("record"))
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda *a, **kw: order.append("watchdog"))
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: order.append(("focus_watchdog", anchor_pid)))

    await browser.get_tab()

    assert order == ["resolve_bundle", "lock", "reap", "anchor", "launch", "record", "watchdog", ("focus_watchdog", 42)]
    assert browser._lock_handle == "fake-lock-handle"
    assert browser._browser.setup_user_dir_called is True
    assert browser._browser._connection_port == 54321
    assert browser._browser._connection_handler == "fake-conn-54321"


@pytest.mark.asyncio
async def test_get_tab_self_launches_with_port_zero_and_forwards_arguments(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: "fake-lock-handle")
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_clear_stale_devtools_port", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    monkeypatch.setattr(browser, "Chrome", lambda options: FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 12345)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")
    monkeypatch.setattr(browser, "_record_own_pids", lambda: None)
    monkeypatch.setattr(browser.death_pipe, "spawn_watchdog", lambda *a, **kw: None)
    monkeypatch.setattr(browser, "_spawn_focus_watchdog", lambda pids, anchor_pid: None)

    await browser.get_tab()

    manager = browser._browser._browser_process_manager
    assert len(manager.start_calls) == 1
    binary_location, port, arguments = manager.start_calls[0]
    assert binary_location == "/fake/Google Chrome"
    assert port == 0
    assert "--no-startup-window" in arguments
    assert f"--user-data-dir={browser.SESSION_DIR}" in arguments
    assert manager.process_creator.func is browser._open_background_process_creator
    assert manager.process_creator.args == (Path("/fake/chromium-1228/Google Chrome for Testing.app"),)


@pytest.mark.asyncio
async def test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor(monkeypatch):
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: "fake-lock-handle")
    monkeypatch.setattr(browser, "_reap_session_profile", lambda: None)
    monkeypatch.setattr(browser, "_clear_stale_devtools_port", lambda: None)
    monkeypatch.setattr(browser, "_get_frontmost_pid", lambda: 999)
    monkeypatch.setattr(browser, "Chrome", lambda options: FakeChrome(options))
    monkeypatch.setattr(browser, "BrowserProcessManager", FakeProcessManager)
    monkeypatch.setattr(browser, "_wait_for_devtools_port", lambda user_data_dir, timeout_s: 54321)
    monkeypatch.setattr(browser, "ConnectionHandler", lambda port: f"fake-conn-{port}")

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
    _reset_state(monkeypatch, browser)
    monkeypatch.setattr(browser, "_browser", FakeChrome(None))
    called = []
    monkeypatch.setattr(browser.browser_lock, "acquire", lambda *a, **kw: called.append(1))
    await browser.get_tab()
    assert called == []
