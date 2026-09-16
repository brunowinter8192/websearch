# ---------------------------------------------------------------------------
# Shared test helper: bypass the real self-launch/port-wait/teardown mechanics so the default cdp
# path can be exercised (AsyncWebCrawler mocked separately, per test) without spawning a real
# browser — mirrors how AsyncWebCrawler itself is already mocked throughout this file.
# ---------------------------------------------------------------------------

def _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process):
    async def _fake_resolve_bundle():
        return chromium_process.Path("/fake/chromium-1228/Google Chrome for Testing.app")

    monkeypatch.setattr(chromium_scrape, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    monkeypatch.setattr(chromium_scrape, "_self_launch_chrome", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "_wait_for_devtools_port", lambda *a, **kw: 9999)
    monkeypatch.setattr(chromium_scrape, "_kill_by_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "_pids_on_profile", lambda *a, **kw: [])
    monkeypatch.setattr(chromium_scrape, "_reap_orphaned_scrapes", lambda: None)
    monkeypatch.setattr(chromium_scrape.death_pipe, "spawn_watchdog", lambda *a, **kw: None)


class _FakeMarkdown:
    def __init__(self, raw_markdown, fit_markdown=None):
        self.raw_markdown = raw_markdown
        self.fit_markdown = fit_markdown if fit_markdown is not None else raw_markdown


class _FakeResult:
    def __init__(self, raw_markdown, status_code=200, success=True, error_message=None, html="",
                 redirected_url=None, response_headers=None):
        self.markdown = _FakeMarkdown(raw_markdown)
        self.status_code = status_code
        self.success = success
        self.error_message = error_message
        self.html = html
        self.response_headers = response_headers if response_headers is not None else {}
        self.crawl_stats = {"attempts": 1, "resolved_by": "direct", "fallback_fetch_used": False}
        self.redirected_url = redirected_url


def _meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "content_type": "text/html",
        "raw_markdown_bytes": 100, "og_published_time": None,
        "crawl4ai_success": True, "crawl4ai_error_message": None,
        "crawl4ai_attempts": 1, "crawl4ai_resolved_by": "direct",
        "crawl4ai_fallback_fetch_used": False, "landed_url": None,
        "document_status_chain": [200], "config": {},
    }
    base.update(overrides)
    return base
