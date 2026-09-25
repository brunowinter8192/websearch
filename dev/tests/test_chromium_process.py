import time

import pytest

from src.scraper import chromium_process, chromium_scrape


def test_wait_for_devtools_port_reads_real_port_file(tmp_path):
    port_file = tmp_path / "DevToolsActivePort"
    port_file.write_text("54321\n/devtools/browser/fake-uuid\n")
    port = chromium_process._wait_for_devtools_port(str(tmp_path), timeout_s=2.0)
    assert port == 54321


def test_wait_for_devtools_port_times_out_when_file_never_appears(tmp_path):
    with pytest.raises(TimeoutError, match="DevToolsActivePort did not appear"):
        chromium_process._wait_for_devtools_port(str(tmp_path), timeout_s=0.3)


def test_find_app_bundle_walks_up_to_app_suffix():
    bundle = chromium_process._find_app_bundle(
        "/Users/x/Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
    assert str(bundle).endswith("Google Chrome for Testing.app")


def test_find_app_bundle_returns_none_when_no_app_ancestor():
    assert chromium_process._find_app_bundle("/usr/local/bin/chrome") is None


def test_build_browser_flags_symbol_resolves_and_is_callable():
    from crawl4ai.browser_manager import ManagedBrowser
    import inspect

    assert hasattr(ManagedBrowser, "build_browser_flags")
    sig = inspect.signature(ManagedBrowser.build_browser_flags)
    params = list(sig.parameters)
    assert params, "build_browser_flags must accept at least one parameter (the BrowserConfig)"

    flags = ManagedBrowser.build_browser_flags(chromium_scrape.BrowserConfig(enable_stealth=True))
    assert isinstance(flags, list)
    assert all(isinstance(f, str) for f in flags)
    assert len(flags) > 0


def test_build_self_launch_flags_keeps_gpu_on_under_stealth():
    flags = chromium_process._build_self_launch_flags(chromium_scrape.BrowserConfig(enable_stealth=True))
    assert "--disable-gpu" not in flags
    assert "--disable-gpu-compositing" not in flags
    assert "--disable-software-rasterizer" not in flags
    assert "--disable-blink-features=AutomationControlled" in flags


def test_build_self_launch_flags_includes_window_size_when_viewport_set():
    config = chromium_scrape.BrowserConfig(enable_stealth=True, viewport_width=1080, viewport_height=600)
    flags = chromium_process._build_self_launch_flags(config)
    assert "--window-size=1080,600" in flags


def test_pids_on_profile_parses_pgrep_output(monkeypatch):
    class _FakeCompleted:
        stdout = "111\n222\n"

    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert chromium_process._pids_on_profile("/tmp/some-dir") == [111, 222]


def test_pids_on_profile_empty_when_no_match(monkeypatch):
    class _FakeCompleted:
        stdout = ""

    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert chromium_process._pids_on_profile("/tmp/some-dir") == []


def test_kill_by_profile_delegates_to_death_pipe_terminate_then_kill(monkeypatch):
    monkeypatch.setattr(chromium_process, "_pids_on_profile", lambda d: [42])
    calls = []
    monkeypatch.setattr(chromium_process.death_pipe, "terminate_then_kill", lambda pids, timeout_s=5.0: calls.append((pids, timeout_s)))
    chromium_process._kill_by_profile("/tmp/some-dir")
    assert calls == [([42], 3.0)]


def test_kill_by_profile_noop_when_no_pids(monkeypatch):
    monkeypatch.setattr(chromium_process, "_pids_on_profile", lambda d: [])
    calls = []
    monkeypatch.setattr(chromium_process.death_pipe, "terminate_then_kill", lambda *a, **kw: calls.append(1))
    chromium_process._kill_by_profile("/tmp/some-dir")
    assert calls == []


def test_reap_orphaned_scrapes_kills_only_pids_older_than_budget(monkeypatch, tmp_path):
    now = time.time()
    young_pid, old_pid = 1001, 1002

    class _FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            return now - (10.0 if self.pid == young_pid else chromium_process.TOTAL_SCRAPE_BUDGET_S + 5.0)

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [young_pid, old_pid])
    monkeypatch.setattr(chromium_process.psutil, "Process", _FakeProc)
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: set())
    killed = []
    monkeypatch.setattr(chromium_process.death_pipe, "terminate_then_kill", lambda pids: killed.append(pids))
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert killed == [[old_pid]]


def test_reap_orphaned_scrapes_never_kills_pid_under_budget_even_if_only_candidate(monkeypatch, tmp_path):
    now = time.time()

    class _FakeProc:
        def create_time(self):
            return now - 5.0

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [2001])
    monkeypatch.setattr(chromium_process.psutil, "Process", lambda pid: _FakeProc())
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: {"/tmp/scrape-url-cdp-live"})
    killed = []
    monkeypatch.setattr(chromium_process.death_pipe, "terminate_then_kill", lambda pids: killed.append(pids))
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert killed == []


def test_reap_orphaned_scrapes_sweeps_dirs_with_no_live_process(monkeypatch, tmp_path):
    live_dir = tmp_path / "scrape-url-cdp-live"
    orphan_dir = tmp_path / "scrape-url-cdp-orphan"
    live_dir.mkdir()
    orphan_dir.mkdir()

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [])
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: {str(live_dir)})
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert live_dir.exists()
    assert not orphan_dir.exists()


def test_live_scrape_profile_dirs_reads_user_data_dir_from_cmdline(monkeypatch):
    class _FakeProc:
        def cmdline(self):
            return ["/fake/Chrome", "--remote-debugging-port=0", "--user-data-dir=/tmp/scrape-url-cdp-abc123", "--flag"]

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [7777])
    monkeypatch.setattr(chromium_process.psutil, "Process", lambda pid: _FakeProc())

    assert chromium_process._live_scrape_profile_dirs() == {"/tmp/scrape-url-cdp-abc123"}


def test_live_scrape_profile_dirs_skips_already_dead_pid(monkeypatch):
    def raise_no_such_process(pid):
        raise chromium_process.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [8888])
    monkeypatch.setattr(chromium_process.psutil, "Process", raise_no_such_process)

    assert chromium_process._live_scrape_profile_dirs() == set()


def _osascript_result(returncode, stdout="", stderr=""):
    class _R:
        pass
    r = _R()
    r.returncode, r.stdout, r.stderr = returncode, stdout, stderr
    return r


def test_get_frontmost_app_warns_once_on_empty_output(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(chromium_process, "_osascript_warned", set())
    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _osascript_result(0, ""))
    with caplog.at_level(logging.WARNING, logger="src.scraper.chromium_process"):
        assert chromium_process._get_frontmost_app() == ""
        assert chromium_process._get_frontmost_app() == ""
    assert len([m for m in caplog.messages if "get_frontmost" in m]) == 1


def test_get_frontmost_app_warns_on_nonzero_exit(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(chromium_process, "_osascript_warned", set())
    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _osascript_result(1, "", "not allowed"))
    with caplog.at_level(logging.WARNING, logger="src.scraper.chromium_process"):
        chromium_process._get_frontmost_app()
    assert any("not allowed" in m for m in caplog.messages)


def test_get_frontmost_app_silent_on_success(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(chromium_process, "_osascript_warned", set())
    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _osascript_result(0, "Ghostty\n"))
    with caplog.at_level(logging.WARNING, logger="src.scraper.chromium_process"):
        assert chromium_process._get_frontmost_app() == "Ghostty"
    assert caplog.messages == []


def test_activate_app_warns_once_on_nonzero_exit(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(chromium_process, "_osascript_warned", set())
    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _osascript_result(1, "", "denied"))
    with caplog.at_level(logging.WARNING, logger="src.scraper.chromium_process"):
        chromium_process._activate_app("Ghostty")
        chromium_process._activate_app("Ghostty")
    assert len(caplog.messages) == 1
