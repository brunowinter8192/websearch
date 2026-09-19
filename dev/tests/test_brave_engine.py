"""Tests for src/search/engines/brave.py's pure result-parsing logic.

No network, no browser — _build_results (JSON items, as if already parsed from the page, into
SearchResult list) is the one seam factored out of the DOM-driven engine. _classify_diagnosis was
removed (the guessed-verdict-removal milestone): its output was one of the EMPTY_* sub-statuses
that no longer exist — the marker/pow_link/ready_state facts it classified are still available
directly in the diagnosis snapshot.
"""
import asyncio
import http.server
import logging
import threading
import time

import pytest
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import TargetCommands

from src.search.engines import brave as brave_mod
from src.search.engines.brave import BraveEngine, _build_results

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# _build_results
# ---------------------------------------------------------------------------

def test_build_results_maps_fields_and_position():
    items = [
        {"url": "https://realpython.com/async-io-python/", "title": "Asyncio Walkthrough", "snippet": "Explore how..."},
        {"url": "https://docs.python.org/3/library/asyncio.html", "title": "asyncio docs", "snippet": "Reference."},
    ]
    results = _build_results(items, max_results=10)
    assert len(results) == 2
    assert results[0].url == "https://realpython.com/async-io-python/"
    assert results[0].title == "Asyncio Walkthrough"
    assert results[0].snippet == "Explore how..."
    assert results[0].engine == "brave"
    assert results[0].position == 1
    assert results[1].position == 2


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


_OWN_QUERY = "cloudflare turnstile captcha widget verify programmatically"
_MARKER_IN_OWN_QUERY_HTML = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{_OWN_QUERY} - Brave Search</title></head>
<body>
<div data-type="web">
  <a href="https://example.org/one" class="search-snippet-title">Cloudflare Turnstile Docs</a>
  <div class="snippet-content"><div class="content">How to verify a Cloudflare Turnstile captcha widget programmatically.</div></div>
</div>
<div data-type="web">
  <a href="https://example.org/two" class="search-snippet-title">Turnstile Widget Guide</a>
  <div class="generic-snippet"><div class="content">Step by step captcha widget verification.</div></div>
</div>
</body>
</html>
"""

_UNRELATED_QUERY = "DS18B20 1-wire dropout compressor fridge electrical noise relay switching"
_MARKER_IN_UNRELATED_SNIPPET_HTML = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{_UNRELATED_QUERY} - Brave Search</title></head>
<body>
<div data-type="web">
  <a href="https://example.org/forum-thread" class="search-snippet-title">DS18B20 dropout after compressor relay switch</a>
  <div class="snippet-content"><div class="content">Reply below. This site is protected by reCAPTCHA and the Google Privacy Policy apply.</div></div>
</div>
<div data-type="web">
  <a href="https://example.org/ds18b20-noise" class="search-snippet-title">Electrical noise causes 1-wire dropout</a>
  <div class="generic-snippet"><div class="content">Add a pull-up resistor and shield the sensor cable.</div></div>
</div>
</body>
</html>
"""

_GENUINE_BLOCK_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Brave Search</title></head>
<body>
<div id="page">
  <p>Rate limit exceeded.</p>
  <a href="/api/captcha/pow-captcha?brave=0">proof of work</a>
</div>
</body>
</html>
"""

_ROUTES = {
    "/marker_in_own_query.html": _MARKER_IN_OWN_QUERY_HTML,
    "/marker_in_unrelated_snippet.html": _MARKER_IN_UNRELATED_SNIPPET_HTML,
    "/genuine_block.html": _GENUINE_BLOCK_HTML,
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


def _patch_brave_tab_lifecycle(monkeypatch, browser: Chrome) -> None:
    monkeypatch.setattr(brave_mod, "new_tab", lambda: _fixture_new_tab(browser))
    monkeypatch.setattr(brave_mod, "kill_tab", lambda tab: _fixture_kill_tab(browser, tab))


@pytest.mark.asyncio
async def test_marker_word_from_own_query_no_longer_discards_real_results(monkeypatch):
    server, base_url = _start_fixture_server()
    browser = await _start_headless_browser()
    try:
        _patch_brave_tab_lifecycle(monkeypatch, browser)
        monkeypatch.setattr(brave_mod, "SEARCH_URL", f"{base_url}/marker_in_own_query.html?q={{}}")
        results, reason, diagnosis = await BraveEngine().search_with_reason(_OWN_QUERY)
    finally:
        await _stop_headless_browser(browser)
        _stop_fixture_server(server)

    assert reason is None
    assert len(results) == 2
    assert {r.url for r in results} == {"https://example.org/one", "https://example.org/two"}
    assert diagnosis == {"document_status_chain": [200], "http_status": 200}


@pytest.mark.asyncio
async def test_marker_word_in_unrelated_organic_snippet_no_longer_discards_real_results(monkeypatch):
    server, base_url = _start_fixture_server()
    browser = await _start_headless_browser()
    try:
        _patch_brave_tab_lifecycle(monkeypatch, browser)
        monkeypatch.setattr(brave_mod, "SEARCH_URL", f"{base_url}/marker_in_unrelated_snippet.html?q={{}}")
        results, reason, diagnosis = await BraveEngine().search_with_reason(_UNRELATED_QUERY)
    finally:
        await _stop_headless_browser(browser)
        _stop_fixture_server(server)

    assert reason is None
    assert len(results) == 2
    assert diagnosis == {"document_status_chain": [200], "http_status": 200}


@pytest.mark.asyncio
async def test_genuine_pow_link_block_still_yields_no_results(monkeypatch):
    assert brave_mod.MAX_WAIT_CYCLES == 20
    assert brave_mod.WAIT_INTERVAL == 0.3
    server, base_url = _start_fixture_server()
    browser = await _start_headless_browser()
    try:
        _patch_brave_tab_lifecycle(monkeypatch, browser)
        monkeypatch.setattr(brave_mod, "SEARCH_URL", f"{base_url}/genuine_block.html?q={{}}")
        t0 = time.perf_counter()
        results, reason, diagnosis = await asyncio.wait_for(
            BraveEngine().search_with_reason("any query at all"), timeout=6.0
        )
        elapsed = time.perf_counter() - t0
    finally:
        await _stop_headless_browser(browser)
        _stop_fixture_server(server)

    assert reason is None
    assert results == []
    assert diagnosis["pow_link"] is True
    assert diagnosis["marker"] is not None
    assert diagnosis["containers_found"] is False
    assert diagnosis["title"] == "Brave Search"
    assert elapsed < 1.0
