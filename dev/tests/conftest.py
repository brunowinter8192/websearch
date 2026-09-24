import pytest

from src.search import browser
from src.scraper import chromium_scrape
from src.scraper import camoufox_scrape
from src.crawler import pipe_scraper


def _launch_trap(qualified_name: str):
    def _trap(*args, **kwargs):
        pytest.fail(
            f"real browser launch attempted via {qualified_name} — this test must mock it before "
            f"reaching here",
            pytrace=False,
        )
    return _trap


@pytest.fixture(autouse=True)
def _no_real_browser_launch(monkeypatch):
    monkeypatch.setattr(browser, "Chrome", _launch_trap("src.search.browser.Chrome"))
    monkeypatch.setattr(chromium_scrape, "_self_launch_chrome",
                         _launch_trap("src.scraper.chromium_scrape._self_launch_chrome"))
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _launch_trap("src.scraper.camoufox_scrape.AsyncCamoufox"))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler",
                         _launch_trap("src.crawler.pipe_scraper.AsyncWebCrawler"))
