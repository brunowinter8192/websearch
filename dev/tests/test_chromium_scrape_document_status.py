import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeResult, _meta


# ---------------------------------------------------------------------------
# document_status_chain — the before_goto hook (_make_document_status_listener) collects the
# ordered chain of main-frame document response statuses; the LAST entry overrides meta["status_code"]
# (the page whose content was actually captured), and an empty chain falls back to crawl4ai's own
# result.status_code unchanged. Exercised through the real _acquire_cdp_headed/_acquire_scrape
# machinery: the fake crawler invokes crawler_strategy.execute_hook("before_goto", ...) itself
# (the same call crawl4ai's own async_crawler_strategy.py makes right before page.goto), against a
# fake page whose .on("response", ...) registers the real listener, then fires fake response events.
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, resource_type, frame):
        self.resource_type = resource_type
        self._frame = frame

    @property
    def frame(self):
        return self._frame


class _FakeResponse:
    def __init__(self, status, request):
        self.status = status
        self.request = request


class _FakeMainFrame:
    pass


class _FakePage:
    def __init__(self):
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


def _fake_crawler_with_document_responses(statuses, crawl4ai_status_code=403):
    """Builds a fake AsyncWebCrawler class whose arun() invokes the real before_goto hook
    registered on the crawler_strategy passed in, fires one fake main-frame document response per
    status in `statuses` (in order), then returns a result carrying crawl4ai_status_code as its
    OWN status_code (simulating crawl4ai's earliest-hop value, distinct from the chain's last)."""
    class _FakeCrawler:
        def __init__(self, *a, **kw):
            self.crawler_strategy = kw.get("crawler_strategy")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            page = _FakePage()
            await self.crawler_strategy.execute_hook(
                "before_goto", page, context=None, url=url, config=config
            )
            for status in statuses:
                page.fire_response(status)
            return _FakeResult(raw_markdown="x" * 300, status_code=crawl4ai_status_code)

    return _FakeCrawler


@pytest.mark.asyncio
async def test_acquire_cdp_headed_last_document_response_overrides_crawl4ai_status(monkeypatch):
    """403 -> 302 -> 200 chain (self-resolving challenge shape): status_code becomes the LAST
    response's status (200), the chain is recorded in full, and crawl4ai's own (earliest-hop) 403
    is overridden — the page whose content was actually captured is the 200 one."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([403, 302, 200], crawl4ai_status_code=403),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [403, 302, 200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_cdp_headed_single_response_chain(monkeypatch):
    """An ordinary page with no challenge/redirect: one main-frame document response, chain has
    exactly one entry, status_code equals today's (unchanged) behavior."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([200], crawl4ai_status_code=200),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_cdp_headed_falls_back_to_crawl4ai_status_when_listener_saw_nothing(monkeypatch):
    """The listener sees no main-frame document response at all (e.g. a raw: input, or a
    navigation that never fires one) — chain stays empty, status_code falls back to crawl4ai's own
    result.status_code, never invented."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([], crawl4ai_status_code=403),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == []
    assert meta["status_code"] == 403


@pytest.mark.asyncio
async def test_document_status_listener_ignores_non_document_and_non_main_frame_responses(monkeypatch):
    """A stylesheet/script response and a document response on a DIFFERENT frame (e.g. an iframe)
    must not enter the chain — only main-frame document responses count."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            self.crawler_strategy = kw.get("crawler_strategy")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            page = _FakePage()
            await self.crawler_strategy.execute_hook(
                "before_goto", page, context=None, url=url, config=config
            )
            page.fire_response(999, resource_type="stylesheet")
            page.fire_response(500, resource_type="document", frame=object())  # iframe, not main
            page.fire_response(200, resource_type="document")
            return _FakeResult(raw_markdown="x" * 300, status_code=200)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [200]


@pytest.mark.asyncio
async def test_try_scrape_document_status_chain_empty_on_launch_failure(monkeypatch):
    """A path that never obtains a result object (browser_missing) carries an empty chain, same
    treatment as every other acquisition-error field."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("BrowserType.launch: Executable doesn't exist at /fake/chrome")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["document_status_chain"] == []


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_document_status_chain(monkeypatch):
    """scrape_url_chromium_workflow's log_scrape record carries the new fact field."""
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta(document_status_chain=[403, 302, 200])

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert captured["document_status_chain"] == [403, 302, 200]


@pytest.mark.asyncio
async def test_try_scrape_calls_reap_orphaned_scrapes_at_start(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
    calls = []
    monkeypatch.setattr(chromium_scrape, "_reap_orphaned_scrapes", lambda: calls.append(1))

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("boom")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)
    await chromium_scrape.try_scrape("https://example.com")

    assert calls == [1]
