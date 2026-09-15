"""Autouse tripwire: no test in this suite may launch a real browser.

Each real browser-launch primitive this project owns is replaced, for every test, with a callable
that fails the test loudly and by name if it is ever reached unmocked. A test that legitimately
exercises browser-launching code overrides the relevant primitive itself via its own
monkeypatch.setattr call inside the test body — that call runs after this fixture's own setup (a
standard pytest fixture guarantee), so it wins for the duration of that test and the trap below
never fires for it.

This exists because a launch that tears itself down in its own finally leaves nothing behind to
find after the fact — a real search_web_workflow call opened and closed three real Chrome windows
across dev/tests/test_query_logger.py alone, invisible to a grep-only audit of the suite. See
process-docs/browser_posture/ for the investigation.
"""
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
