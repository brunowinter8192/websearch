from datetime import datetime, timezone


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class _FakeMarkdown:
    def __init__(self, raw_markdown):
        self.raw_markdown = raw_markdown


class _FakeResult:
    def __init__(self, raw_markdown, status_code=200, success=True, error_message=None,
                 redirected_url=None, links=None):
        self.markdown = _FakeMarkdown(raw_markdown)
        self.status_code = status_code
        self.success = success
        self.error_message = error_message
        self.crawl_stats = {"attempts": 1, "resolved_by": "direct", "fallback_fetch_used": False}
        self.redirected_url = redirected_url
        self.links = links if links is not None else {"internal": [], "external": []}


class _FakeCrawler:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        if "fail" in url:
            raise Exception("simulated network failure")
        return _FakeResult(raw_markdown="x" * 500)


def _camoufox_meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "landed_url": "https://x.test/a",
        "raw_markdown_bytes": 100, "markdown_conversion_error": None,
        "document_status_chain": [200],
        "config": {"headless": False, "os": "macos"}, "config_hash": "cafef00d00",
    }
    base.update(overrides)
    return base
