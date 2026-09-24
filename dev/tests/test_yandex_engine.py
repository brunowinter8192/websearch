import asyncio
import http.server
import logging
import threading

import pytest
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import TargetCommands

from src.search.engines import yandex as yandex_mod
from src.search.engines.yandex import YandexEngine, _build_results, _is_block_url, _is_self_referential

logger = logging.getLogger(__name__)


def test_is_self_referential_matches_yandex_domain():
    assert _is_self_referential("https://yandex.com/video/preview/123?text=q") is True


def test_is_self_referential_matches_yandex_subdomain():
    assert _is_self_referential("https://translate.yandex.com/translate?url=x") is True


def test_is_self_referential_does_not_match_lookalike_domain():
    assert _is_self_referential("https://notyandex.com/page") is False


def test_is_self_referential_does_not_match_real_external_domain():
    assert _is_self_referential("https://realpython.com/async-io-python/") is False


def test_is_block_url_detects_showcaptcha_redirect():
    assert _is_block_url("https://yandex.com/showcaptcha?cc=1&mt=abc") is True


def test_is_block_url_false_for_normal_search_url():
    assert _is_block_url("https://yandex.com/search/?text=python") is False


def test_is_block_url_false_when_marker_word_only_in_query_string():
    assert _is_block_url(
        "https://yandex.com/search/?text=yandex+showcaptcha+spravka+cookie+after+solving+captcha&lr=100"
    ) is False


def test_is_block_url_true_for_real_captcha_path_regardless_of_query_string():
    assert _is_block_url("https://yandex.com/showcaptcha?form-fb-hint=1.1&mt=abcdef") is True


def test_build_results_maps_fields_and_position():
    items = [
        {"url": "https://realpython.com/async-io-python/", "title": "Asyncio Walkthrough", "snippet": "Explore how..."},
        {"url": "https://docs.python.org/3/library/asyncio.html", "title": "asyncio docs", "snippet": "Reference."},
    ]
    results = _build_results(items, max_results=10)
    assert len(results) == 2
    assert results[0].url == "https://realpython.com/async-io-python/"
    assert results[0].engine == "yandex"
    assert results[0].position == 1
    assert results[1].position == 2


def test_build_results_drops_yandex_self_referential_urls():
    items = [
        {"url": "https://realpython.com/async-io-python/", "title": "real result", "snippet": ""},
        {"url": "https://yandex.com/video/preview/123?text=q", "title": "video carousel card", "snippet": ""},
        {"url": "https://docs.python.org/3/library/asyncio.html", "title": "another real result", "snippet": ""},
    ]
    results = _build_results(items, max_results=10)
    urls = [r.url for r in results]
    assert "https://yandex.com/video/preview/123?text=q" not in urls
    assert len(results) == 2
    assert [r.position for r in results] == [1, 2]


def test_build_results_skips_items_without_url():
    items = [{"url": "", "title": "no url", "snippet": ""}, {"url": "https://example.com", "title": "ok", "snippet": ""}]
    results = _build_results(items, max_results=10)
    assert len(results) == 1
    assert results[0].url == "https://example.com"


def test_build_results_respects_max_results_cap():
    items = [{"url": f"https://example.com/{i}", "title": str(i), "snippet": ""} for i in range(20)]
    results = _build_results(items, max_results=5)
    assert len(results) == 5
    assert [r.position for r in results] == [1, 2, 3, 4, 5]


_OWN_QUERY = "yandex showcaptcha spravka cookie after solving captcha"
_RESULTS_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>yandex showcaptcha spravka cookie after solving captcha — Yandex: found 1 million results</title></head>
<body>
<li class="serp-item">
  <a class="OrganicTitle-Link" href="https://example.org/one">Spravka cookie explainer</a>
  <div class="OrganicText">What the spravka cookie means after solving a captcha challenge.</div>
</li>
<li class="serp-item">
  <a class="OrganicTitle-Link" href="https://example.org/two">Yandex showcaptcha guide</a>
  <div class="OrganicText">Steps to clear a showcaptcha redirect.</div>
</li>
</body>
</html>
"""

_GENUINE_BLOCK_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Are you not a robot?</title></head>
<body>
<div id="checkbox-captcha"><p>Confirm you are not a robot to continue.</p></div>
</body>
</html>
"""

_ROUTES = {
    "/search/": _RESULTS_HTML,
    "/showcaptcha": _GENUINE_BLOCK_HTML,
}


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    routes: dict[str, str] = _ROUTES

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        body = self.routes.get(path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        return


def _start_fixture_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


def _stop_fixture_server(server: http.server.ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


async def _start_headless_browser() -> Chrome:
    options = ChromiumOptions()
    options.headless = True
    browser = Chrome(options)
    await browser.start()
    return browser


async def _stop_headless_browser(browser: Chrome) -> None:
    await browser.stop()


async def _fixture_new_tab(browser: Chrome):
    return await browser.new_tab()


async def _fixture_kill_tab(browser: Chrome, tab) -> None:
    target_id = getattr(tab, "_target_id", None)
    if target_id is None:
        return
    try:
        await asyncio.wait_for(browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0)
    except Exception as e:
        logger.warning("fixture kill_tab close_target failed (target_id=%s): %s", target_id, e)


def _patch_yandex_tab_lifecycle(monkeypatch, browser: Chrome) -> None:
    monkeypatch.setattr(yandex_mod, "new_tab", lambda: _fixture_new_tab(browser))
    monkeypatch.setattr(yandex_mod, "kill_tab", lambda tab: _fixture_kill_tab(browser, tab))


@pytest.mark.browser
@pytest.mark.asyncio
async def test_marker_word_in_own_query_no_longer_discards_real_results(monkeypatch):
    server, base_url = _start_fixture_server()
    browser = await _start_headless_browser()
    try:
        _patch_yandex_tab_lifecycle(monkeypatch, browser)
        monkeypatch.setattr(yandex_mod, "SEARCH_URL", f"{base_url}/search/?text={{}}")
        results, reason, diagnosis = await YandexEngine().search_with_reason(_OWN_QUERY)
    finally:
        await _stop_headless_browser(browser)
        _stop_fixture_server(server)

    assert reason is None
    assert len(results) == 2
    assert {r.url for r in results} == {"https://example.org/one", "https://example.org/two"}
    assert diagnosis == {"document_status_chain": [200], "http_status": 200}


@pytest.mark.browser
@pytest.mark.asyncio
async def test_genuine_showcaptcha_redirect_still_yields_no_results(monkeypatch):
    server, base_url = _start_fixture_server()
    browser = await _start_headless_browser()
    try:
        _patch_yandex_tab_lifecycle(monkeypatch, browser)
        monkeypatch.setattr(yandex_mod, "SEARCH_URL", f"{base_url}/showcaptcha?text={{}}")
        results, reason, diagnosis = await YandexEngine().search_with_reason("any query at all")
    finally:
        await _stop_headless_browser(browser)
        _stop_fixture_server(server)

    assert reason is None
    assert results == []
    assert diagnosis["containers_found"] is None
    assert diagnosis["title"] == "Are you not a robot?"
