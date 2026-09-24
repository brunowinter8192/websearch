import asyncio


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
