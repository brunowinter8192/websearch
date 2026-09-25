# INFRASTRUCTURE
import asyncio

import pytest

from src.news.platforms.coindesk import browser as feed_browser


# FUNCTIONS

def test_no_captured_request_returns_empty_triple_and_cleans_up(harness):
    log, state = harness
    result = asyncio.run(feed_browser.browser_load_feed(3))
    assert result == ({}, "", None)
    assert log == ["launch", "open", "capture:3", "tab.close", "chrome.close", "kill:4321", "rmtree"]


def test_successful_replay_returns_headers_url_and_body(harness):
    log, state = harness
    state["entry"] = _entry()
    headers, url, body = asyncio.run(feed_browser.browser_load_feed(2))
    assert url == "https://api/x"
    assert body == b"body"
    assert "X-Keep" in headers
    assert log[-4:] == ["tab.close", "chrome.close", "kill:4321", "rmtree"]


def test_non_200_replay_returns_no_body(harness, capsys):
    log, state = harness
    state["entry"] = _entry()
    state["response"] = _FakeResponse(403)
    headers, url, body = asyncio.run(feed_browser.browser_load_feed(2))
    assert body is None
    assert url == "https://api/x"
    assert "first replay → 403" in capsys.readouterr().err


def test_connect_failure_propagates_and_still_cleans_up(harness):
    log, state = harness
    state["fail_connect"] = True
    with pytest.raises(RuntimeError, match="connect failed"):
        asyncio.run(feed_browser.browser_load_feed(2))
    assert log == ["launch", "chrome.close", "kill:4321", "rmtree"]


def test_tab_close_failure_is_reported_and_cleanup_continues(harness, capsys):
    log, state = harness
    state["fail_tab_close"] = True
    asyncio.run(feed_browser.browser_load_feed(1))
    assert "tab.close (non-fatal): close failed" in capsys.readouterr().err
    assert log[-3:] == ["chrome.close", "kill:4321", "rmtree"]


@pytest.fixture
def harness(monkeypatch, tmp_path):
    log = []
    state = {"entry": None, "response": _FakeResponse(200), "fail_connect": False, "fail_tab_close": False}

    monkeypatch.setattr(feed_browser, "get_free_port", lambda: 4321)
    monkeypatch.setattr(feed_browser.tempfile, "mkdtemp", lambda prefix: str(tmp_path))
    monkeypatch.setattr(feed_browser, "launch_background_chrome", lambda port, session_dir: log.append("launch"))
    monkeypatch.setattr(feed_browser, "wait_for_ws_url", lambda port: "ws://x")
    monkeypatch.setattr(feed_browser, "kill_chrome_on_port", lambda port: log.append(f"kill:{port}"))
    monkeypatch.setattr(feed_browser.shutil, "rmtree", lambda path, ignore_errors=False: log.append("rmtree"))

    tab = _FakeTab(log)

    def make_chrome():
        tab.fail = state["fail_tab_close"]
        return _FakeChrome(log, tab, fail_connect=state["fail_connect"])

    async def fake_open(t):
        log.append("open")

    async def fake_capture(t, n_clicks):
        log.append(f"capture:{n_clicks}")
        return state["entry"]

    monkeypatch.setattr(feed_browser, "Chrome", make_chrome)
    monkeypatch.setattr(feed_browser, "_open_feed_page", fake_open)
    monkeypatch.setattr(feed_browser, "capture_timeline_request", fake_capture)
    monkeypatch.setattr(feed_browser.httpx, "get", lambda url, **kw: state["response"])
    return log, state


def _entry():
    return {"request": {"url": "https://api/x", "headers": [{"name": "Cookie", "value": "a"}, {"name": "X-Keep", "value": "b"}]}}


class _FakeResponse:
    def __init__(self, status_code, content=b"body"):
        self.status_code = status_code
        self.content = content


class _Closable:
    def __init__(self, log, label, fail=False):
        self.log = log
        self.label = label
        self.fail = fail

    async def close(self):
        self.log.append(self.label)
        if self.fail:
            raise RuntimeError("close failed")


class _FakeTab(_Closable):
    def __init__(self, log, fail=False):
        super().__init__(log, "tab.close", fail)


class _FakeChrome(_Closable):
    def __init__(self, log, tab, fail_connect=False, fail_close=False):
        super().__init__(log, "chrome.close", fail_close)
        self.tab = tab
        self.fail_connect = fail_connect

    async def connect(self, ws_url):
        if self.fail_connect:
            raise RuntimeError("connect failed")
        return self.tab
