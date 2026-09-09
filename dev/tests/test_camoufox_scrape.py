"""Tests for camoufox_scrape's calibrated core acquisition module — the second, parallel
acquisition lane (Camoufox/Playwright-Firefox) beside crawl4ai's chromium path. No CLI/logging
wiring exists yet (later milestones); this only tests the module boundary itself.

Runs without a real Camoufox browser: camoufox_scrape.AsyncCamoufox and camoufox_scrape.launch_options
are patched with fakes, isolating the module from the real binary/network. camoufox_scrape.AsyncWebCrawler
(the separate throwaway crawler used for raw: markdown conversion) is patched the same way
test_pipe_scraper.py fakes crawl4ai's own AsyncWebCrawler.
"""
import asyncio
import logging

import pytest
from camoufox.exceptions import CamoufoxNotInstalled

from src.scraper import camoufox_scrape


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _fake_launch_options(**kwargs):
    return {"executable_path": "/fake/camoufox/firefox-bin", **kwargs}


class _FakeResponse:
    def __init__(self, status, request=None):
        self.status = status
        self.request = request


class _FakeRequest:
    def __init__(self, resource_type, frame):
        self.resource_type = resource_type
        self._frame = frame

    @property
    def frame(self):
        return self._frame


class _FakeMainFrame:
    pass


class _FakePage:
    """Fires document_statuses (default: just the returned response's own status, the pre-existing
    single-hop shape every earlier test in this file relies on) as main-frame document responses
    DURING goto() — CAMOUFOX_RENDER_WAIT_S is zeroed in every test that uses this fake, so there is
    no real "later" window to fire into; firing the whole intended chain before goto() returns is an
    equivalent, deterministic stand-in for a redirect chain plus a same-document JS navigation that
    resolves during the (zeroed) render wait. Each entry in document_statuses is either a plain int
    (fired as a main-frame document response) or a (status, resource_type, frame) tuple for tests
    proving non-document/non-main-frame responses are excluded from the chain. The RETURNED response
    can carry a DIFFERENT status than document_statuses' last entry — proving the override actually
    happens, not just coincidentally matching."""
    def __init__(self, landed_url, status, html, document_statuses=None):
        self._landed_url = landed_url
        self._status = status
        self._html = html
        self._document_statuses = document_statuses if document_statuses is not None else [status]
        self.url = "about:blank"
        self.main_frame = _FakeMainFrame()
        self._response_handlers = []

    def on(self, event, handler):
        if event == "response":
            self._response_handlers.append(handler)

    def fire_response(self, status, resource_type="document", frame=None):
        request = _FakeRequest(resource_type, frame if frame is not None else self.main_frame)
        response = _FakeResponse(status, request)
        for h in self._response_handlers:
            h(response)

    async def goto(self, url, timeout=None, wait_until=None):
        self.url = self._landed_url
        for entry in self._document_statuses:
            if isinstance(entry, tuple):
                status, resource_type, frame = entry
                self.fire_response(status, resource_type=resource_type, frame=frame)
            else:
                self.fire_response(entry)
        return _FakeResponse(self._status)

    async def content(self):
        return self._html


class _FakeBrowser:
    def __init__(self, page):
        self._page = page

    async def new_page(self):
        return self._page


def _make_fake_camoufox(landed_url="https://x.test/a", status=200,
                         html="<html><body>real page content</body></html>", document_statuses=None):
    """Factory: returns a fake AsyncCamoufox class bound to one fake page's fixed shape."""
    page = _FakePage(landed_url, status, html, document_statuses=document_statuses)
    browser = _FakeBrowser(page)

    class _FakeAsyncCamoufox:
        def __init__(self, **kwargs):
            self.launch_kwargs = kwargs

        async def __aenter__(self):
            return browser

        async def __aexit__(self, *a):
            return False

    return _FakeAsyncCamoufox


class _RaisingAsyncCamoufox:
    def __init__(self, exc):
        self._exc = exc

    def __call__(self, **kwargs):
        return self

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *a):
        return False


class _HangingAsyncCamoufox:
    def __call__(self, **kwargs):
        return self

    async def __aenter__(self):
        await asyncio.sleep(10)

    async def __aexit__(self, *a):
        return False


class _FakeMarkdown:
    def __init__(self, raw_markdown):
        self.raw_markdown = raw_markdown


class _FakeCrawlResult:
    def __init__(self, raw_markdown):
        self.markdown = _FakeMarkdown(raw_markdown)


_FAKE_MARKDOWN_TEXT = "# Fake Markdown\n\nDeterministic content for assertions."


class _FakeAsyncWebCrawler:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        assert url.startswith("raw:")
        return _FakeCrawlResult(_FAKE_MARKDOWN_TEXT)


class _UrlsplitAsyncWebCrawler:
    """Simulates crawl4ai's OWN internal urllib.parse.urlsplit(url) call on the pseudo-URL — the
    real failure mode this guards against: a raw://<html> pseudo-URL where the HTML contains a
    bare "[" before the first "/" raises ValueError("Invalid IPv6 URL") (Python 3.14's
    _check_bracketed_netloc) before crawl4ai's own raw-html branch ever runs. "raw:" (no netloc)
    does not trigger this parsing at all."""
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        from urllib.parse import urlsplit
        urlsplit(url)
        return _FakeCrawlResult(_FAKE_MARKDOWN_TEXT)


# ---------------------------------------------------------------------------
# Normal fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_normal_fetch(monkeypatch):
    """A clean fetch: content, status, landed_url, raw_markdown_bytes, config/config_hash all
    populated; acquisition_error stays None."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    # asyncio.sleep(CAMOUFOX_RENDER_WAIT_S) is a real stdlib sleep, not interceptable by the fakes
    # above — zeroed so this test doesn't actually wait 5s.
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == _FAKE_MARKDOWN_TEXT
    assert meta["acquisition_error"] is None
    assert meta["status_code"] == 200
    assert meta["landed_url"] == "https://x.test/a"
    assert meta["raw_markdown_bytes"] == len(_FAKE_MARKDOWN_TEXT.encode("utf-8"))
    assert meta["config"]["executable_path"] == "/fake/camoufox/firefox-bin"
    assert meta["config_hash"] is not None


@pytest.mark.asyncio
async def test_try_scrape_camoufox_captures_landed_url_raw_on_redirect(monkeypatch):
    """landed_url reflects wherever the browser actually ended up — raw, no comparison, no
    verdict, even when it differs from the requested URL (host-change redirect shape)."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://platform.claude.com/docs/en/api/overview", status=301),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    content, meta = await camoufox_scrape.try_scrape_camoufox(
        "https://docs.anthropic.com/en/api/getting-started")

    assert meta["status_code"] == 301
    assert meta["landed_url"] == "https://platform.claude.com/docs/en/api/overview"
    # No verdict field of any kind — this module reports facts only
    assert "same_target" not in meta


# ---------------------------------------------------------------------------
# acquisition_error states
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_budget_exhausted(monkeypatch, caplog):
    """A hang inside the acquisition (Camoufox never returns) is cut off at
    TOTAL_CAMOUFOX_BUDGET_S, yielding acquisition_error=budget_exhausted — not a hang."""
    monkeypatch.setattr(camoufox_scrape, "TOTAL_CAMOUFOX_BUDGET_S", 0.05)
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox", _HangingAsyncCamoufox())

    with caplog.at_level(logging.WARNING, logger="src.scraper.camoufox_scrape"):
        content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "budget_exhausted"
    assert any("budget exhausted" in m.lower() for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_camoufox_detects_binary_missing(monkeypatch, caplog):
    """CamoufoxNotInstalled (raised from launch_options -> launch_path when the browser binary
    hasn't been fetched) maps to acquisition_error=browser_missing, with the fix command named in
    the logged message."""
    def _raise(**kwargs):
        raise CamoufoxNotInstalled(
            "official/stable is not installed. Please run `camoufox fetch` to install.")
    monkeypatch.setattr(camoufox_scrape, "launch_options", _raise)

    with caplog.at_level(logging.ERROR, logger="src.scraper.camoufox_scrape"):
        content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "browser_missing"
    assert any("camoufox fetch" in m for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_camoufox_exception_fail_soft(monkeypatch):
    """A non-launch-missing exception (e.g. a real browser-launch crash) degrades to
    acquisition_error=exception — never propagates to the caller."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _RaisingAsyncCamoufox(RuntimeError("simulated browser crash")))

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "exception"
    assert meta["landed_url"] is None
    assert meta["status_code"] is None


# ---------------------------------------------------------------------------
# Regression: HTML with a bare "[" before the first "/" (e.g. an early inline <script> JS array
# literal, extremely common) used to make crawl4ai's own urlsplit() raise "Invalid IPv6 URL" on a
# raw://<html> pseudo-URL. _html_to_markdown uses "raw:" instead, which carries no netloc and is
# not subject to that parsing at all.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_html_to_markdown_survives_bracket_before_first_slash(monkeypatch):
    """Real trigger shape (idealo.de): an inline <script> with a JS array literal puts "[" before
    the document's first "/". _html_to_markdown must produce a pseudo-URL that survives crawl4ai's
    own urlsplit() call unchanged, converting real content instead of failing."""
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _UrlsplitAsyncWebCrawler)
    html = "<html><head><script>var a = [1,2,3];</script></head><body>content</body></html>"

    content, error = await camoufox_scrape._html_to_markdown(html)

    assert error is None
    assert content == _FAKE_MARKDOWN_TEXT


# ---------------------------------------------------------------------------
# Markdown-conversion failure: acquisition SUCCEEDED (real HTML captured) but crawl4ai's raw:
# pipeline failed. REMOVED 2026-09-09: the raw-HTML-as-content fallback (returning the captured
# HTML as content when conversion failed) — no supporting observation (the only real trigger was
# the raw:// urlsplit bug, fixed 2026-08-07 by the switch to "raw:"; 112 production records since,
# zero with the old content_is_raw_html=True). Conversion failure now surfaces as empty content
# plus markdown_conversion_error, and acquisition_error MUST stay None — acquisition itself
# produced a real result, this is a downstream conversion failure.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_conversion_failure_yields_empty_content(monkeypatch):
    """On a markdown-conversion failure, content is now "" (never the raw captured HTML) and
    markdown_conversion_error carries the fact; acquisition_error stays None; content_is_raw_html
    no longer exists in meta at all."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=200,
                             html="<html><body>real captured page</body></html>"),
    )
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    async def _fake_html_to_markdown(html):
        return "", "simulated conversion failure"
    monkeypatch.setattr(camoufox_scrape, "_html_to_markdown", _fake_html_to_markdown)

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["markdown_conversion_error"] == "simulated conversion failure"
    assert meta["acquisition_error"] is None
    assert "content_is_raw_html" not in meta


# ---------------------------------------------------------------------------
# Calibration surface: _build_camoufox_kwargs / _extract_camoufox_config_stamp
# ---------------------------------------------------------------------------

def test_build_camoufox_kwargs_reflects_block_images_param():
    """block_images is the one parameterized (per-lane) knob; everything else is fixed."""
    off = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    on = camoufox_scrape._build_camoufox_kwargs(block_images=True)
    assert off["block_images"] is False
    assert on["block_images"] is True


def test_build_camoufox_kwargs_fixed_decisions():
    """headless=False (visible window), os="macos" (matches real host), timeout explicit, locale
    resolved (as of 2026-08-27, so this lane requests the same language chromium gets for free from
    the OS) — and the deliberately-left-unset knobs (block_webgl, geoip, humanize, enable_cache,
    proxy) are truly ABSENT from the dict, not just False, so camoufox's own library defaults apply
    untouched."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["headless"] is False
    assert kwargs["os"] == "macos"
    assert kwargs["timeout"] == camoufox_scrape._PLAYWRIGHT_DEFAULT_TIMEOUT_MS
    assert isinstance(kwargs["locale"], str) and kwargs["locale"]
    for absent_key in ("block_webgl", "geoip", "humanize", "enable_cache", "proxy"):
        assert absent_key not in kwargs


def test_extract_camoufox_config_stamp_reads_real_executable_path_not_redeclared():
    """The stamp's executable_path comes off the REAL resolved launch_options() output, not a
    re-declared literal — changing what launch_options() resolves changes the stamp."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    resolved = {"executable_path": "/some/real/resolved/path", "headless": False}
    stamp = camoufox_scrape._extract_camoufox_config_stamp(kwargs, resolved)
    assert stamp["executable_path"] == "/some/real/resolved/path"
    assert stamp["total_budget_s"] == camoufox_scrape.TOTAL_CAMOUFOX_BUDGET_S


def test_extract_camoufox_config_stamp_excludes_randomized_fingerprint_data():
    """The stamp must NOT include per-launch randomized fingerprint data (fonts/seeds/env) even if
    present in the resolved dict — hashing that would make config_hash unique on every call."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    resolved = {
        "executable_path": "/some/path",
        "env": {"CAMOU_CONFIG": '{"canvas:seed": 12345}'},
        "firefox_user_prefs": {"some.random.pref": True},
    }
    stamp = camoufox_scrape._extract_camoufox_config_stamp(kwargs, resolved)
    assert "env" not in stamp
    assert "firefox_user_prefs" not in stamp


@pytest.mark.asyncio
async def test_config_hash_stable_for_identical_kwargs(monkeypatch):
    """Two calls with the same calibration surface produce the same config_hash — a real 'same
    config' grouping key, not per-call noise."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta1 = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")
    _, meta2 = await camoufox_scrape.try_scrape_camoufox("https://x.test/b")

    assert meta1["config_hash"] == meta2["config_hash"]


# ---------------------------------------------------------------------------
# document_status_chain — _make_document_status_listener (registered on the page BEFORE page.goto)
# collects the ordered chain of main-frame document response statuses; the LAST entry overrides
# status_code (the page whose content was actually captured), and an empty chain falls back to the
# goto Response's own status unchanged. Same contract as chromium_scrape.py's M1 fix, driven
# directly through plain Playwright rather than a crawl4ai hook.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_camoufox_last_document_response_overrides_goto_status(monkeypatch):
    """403 -> 302 -> 200 chain (self-resolving challenge shape): status_code becomes the LAST
    response's status (200), the chain is recorded in full, and the goto Response's own (stale) 403
    is overridden — the page whose content was actually captured is the 200 one."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=403,
                             document_statuses=[403, 302, 200]),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [403, 302, 200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_camoufox_single_response_chain(monkeypatch):
    """An ordinary page with no challenge/redirect: one main-frame document response, chain has
    exactly one entry, status_code equals today's (unchanged) behavior."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_camoufox_falls_back_to_goto_status_when_listener_saw_nothing(monkeypatch):
    """The listener sees no main-frame document response at all — chain stays empty, status_code
    falls back to the goto Response's own status, never invented."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=403, document_statuses=[]),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == []
    assert meta["status_code"] == 403


@pytest.mark.asyncio
async def test_acquire_camoufox_ignores_non_document_and_non_main_frame_responses(monkeypatch):
    """A stylesheet response and a document response on a DIFFERENT frame (e.g. an iframe) must not
    enter the chain — only main-frame document responses count."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(
            landed_url="https://x.test/a", status=200,
            document_statuses=[(999, "stylesheet", None), (500, "document", object()), 200],
        ),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [200]


@pytest.mark.asyncio
async def test_try_scrape_camoufox_document_status_chain_empty_on_launch_failure(monkeypatch):
    """A path that never obtains a page/response (browser_missing) carries an empty chain, same
    treatment as every other acquisition-error field."""
    def _raise(**kwargs):
        raise CamoufoxNotInstalled(
            "official/stable is not installed. Please run `camoufox fetch` to install.")
    monkeypatch.setattr(camoufox_scrape, "launch_options", _raise)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["document_status_chain"] == []


# ---------------------------------------------------------------------------
# scrape_url_camoufox_workflow: milestone 2 — the ad-hoc CLI wiring. Logs into the SAME
# scrape_log.jsonl / log_scrape / write_sidecar as chromium_scrape.py's chromium lane, discriminated by
# the "engine" field. try_scrape_camoufox is faked at the module boundary; log_scrape/write_sidecar
# are faked to capture the record instead of touching the filesystem.
# ---------------------------------------------------------------------------

def _meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "landed_url": "https://x.test/a",
        "raw_markdown_bytes": 100, "markdown_conversion_error": None,
        "document_status_chain": [200],
        "config": {"headless": False}, "config_hash": "deadbeef00",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_engine_discriminator(monkeypatch):
    """The logged record carries engine="camoufox" — the first-class discriminator this milestone
    adds, distinguishing it from the chromium lane's engine="chromium" records in the same file."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "real markdown content", _meta()
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["engine"] == "camoufox"
    assert captured["url"] == "https://x.test/a"
    assert captured["mode"] == "markdown"
    assert "outcome" not in captured


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_acquisition_error_as_its_own_fact(monkeypatch):
    """No computed outcome anymore — acquisition_error (try_scrape_camoufox's own fact field:
    "budget_exhausted"/"browser_missing"/"exception", or None) is logged straight through as its
    own field, the same precedent pipe_scraper_records.py's _log_pipe_camoufox_record set."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "", _meta(acquisition_error="budget_exhausted", status_code=None, landed_url=None)
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["acquisition_error"] == "budget_exhausted"


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_document_status_chain(monkeypatch):
    """scrape_url_camoufox_workflow's log_scrape record carries the new fact field."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "real content", _meta(document_status_chain=[403, 302, 200])
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["document_status_chain"] == [403, 302, 200]


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_does_not_double_hash_config(monkeypatch):
    """config_hash is read straight off meta (computed once, inside try_scrape_camoufox) — the
    workflow must not re-hash it itself."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "content", _meta(config_hash="already-computed-hash")
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["config_hash"] == "already-computed-hash"


# ---------------------------------------------------------------------------
# _format_camoufox_output: same fixed-shape philosophy as _format_scrape_output — facts always,
# landed URL unconditional
# ---------------------------------------------------------------------------

def test_format_camoufox_output_normal_markdown_shape():
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "the real markdown content here", _meta())
    assert "- Engine: camoufox" in text
    assert "- HTTP status: 200" in text
    assert "- Landed URL (the URL the browser actually returned content from): https://x.test/a" in text
    assert "Content format" not in text  # the raw-HTML-as-content fallback was removed 2026-09-09
    facts_idx = text.index("## Acquisition facts")
    content_idx = text.index("## Content")
    body_idx = text.index("the real markdown content here")
    assert facts_idx < content_idx < body_idx


def test_format_camoufox_output_landed_url_unconditional_even_when_absent():
    """Same rule as the chromium lane: landed_url renders even when None (absent), literally."""
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "", _meta(landed_url=None, acquisition_error="browser_missing"))
    assert "- Landed URL (the URL the browser actually returned content from): None" in text


def test_format_camoufox_output_renders_document_status_chain_line():
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "the real page content",
        _meta(status_code=200, document_status_chain=[403, 302, 200]))
    assert "Document status chain" in text
    assert "[403, 302, 200]" in text


def test_format_camoufox_output_acquisition_failure_shape():
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "",
        _meta(status_code=None, landed_url=None, raw_markdown_bytes=0,
              acquisition_error="budget_exhausted"))
    assert "(no content returned)" in text
    assert "Acquisition error: camoufox acquisition exceeded the total time budget" in text


# ---------------------------------------------------------------------------
# No-focus-steal launch (milestone 3, Half A) — _find_app_bundle / _ensure_no_focus_steal.
# Uses a real tmp_path .app-shaped bundle + real plistlib round-trip (no fakes needed: plistlib is
# pure Python, no camoufox/OS dependency), pinning the exact mechanism verified empirically this
# session (real osascript/System Events focus-poll: LSUIElement=true stopped Camoufox from ever
# becoming the frontmost application across a real try_scrape_camoufox call).
# ---------------------------------------------------------------------------

def test_find_app_bundle_locates_dotapp_ancestor(tmp_path):
    app = tmp_path / "Camoufox.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "camoufox"
    executable.write_text("")
    assert camoufox_scrape._find_app_bundle(str(executable)) == app


def test_find_app_bundle_returns_none_when_not_in_a_bundle(tmp_path):
    bare = tmp_path / "some_binary"
    bare.write_text("")
    assert camoufox_scrape._find_app_bundle(str(bare)) is None


def _make_fake_app_bundle(tmp_path, existing_plist: dict | None = None):
    import plistlib
    app = tmp_path / "Camoufox.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "camoufox"
    executable.write_text("")
    plist_path = app / "Contents" / "Info.plist"
    with open(plist_path, "wb") as f:
        plistlib.dump(existing_plist or {"CFBundleName": "Camoufox"}, f)
    return str(executable), plist_path


def test_ensure_no_focus_steal_sets_lsuielement(tmp_path, monkeypatch):
    """Fresh bundle, no LSUIElement key -> set to True."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_idempotent(tmp_path, monkeypatch):
    """Already-True bundle -> no write attempted (no exception, value unchanged either way)."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(
        tmp_path, existing_plist={"CFBundleName": "Camoufox", "LSUIElement": True})

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_noop_on_non_macos(tmp_path, monkeypatch):
    """Non-darwin platform -> no-op, no exception, plist untouched."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "linux")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert "LSUIElement" not in data


def test_ensure_no_focus_steal_noop_when_executable_path_missing(monkeypatch):
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    camoufox_scrape._ensure_no_focus_steal(None)  # must not raise
    camoufox_scrape._ensure_no_focus_steal("")     # must not raise


# ---------------------------------------------------------------------------
# Focus-steal launch fix — the LSUIElement plist patch above only suppresses the OS's PASSIVE
# default activation-on-launch policy; playwright#41306 states Firefox's Playwright launcher
# unconditionally injects an EXPLICIT "-foreground" Cocoa activation arg whenever headless=False,
# which overrides that patch. ignore_default_args=["-foreground"] (_build_camoufox_kwargs) is
# playwright's own public opt-out for it. A previously-suspected window-creation-time residual
# (an in-process AXMain-keyed watchdog, _key_window_steal_watchdog, once reclaimed it) was removed
# 2026-08-27 after live human verification found no measurable effect from the watchdog either way
# (process-docs/camoufox_lane/2026-08-26_axmain_is_not_an_activation_signal.md) — AXMain=true on
# this LSUIElement accessory process does not imply real activation.
# ---------------------------------------------------------------------------

def test_build_camoufox_kwargs_ignores_foreground_default_arg():
    """ignore_default_args drops Firefox's own launch-time -foreground activation call — the
    launch-time half of the fix, playwright#41306's documented opt-out mechanism."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["ignore_default_args"] == ["-foreground"]
