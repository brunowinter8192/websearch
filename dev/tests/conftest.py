# INFRASTRUCTURE
import subprocess
import tempfile

import pytest

from src.search import browser
from src.scraper import chromium_scrape
from src.scraper import camoufox_scrape
from src.crawler import pipe_scraper


# FUNCTIONS

@pytest.fixture(autouse=True)
def _no_real_browser_launch(monkeypatch):
    monkeypatch.setattr(browser, "Chrome", _launch_trap("src.search.browser.Chrome"))
    monkeypatch.setattr(chromium_scrape, "self_launch_chrome",
                         _launch_trap("src.scraper.chromium_scrape.self_launch_chrome"))
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _launch_trap("src.scraper.camoufox_scrape.AsyncCamoufox"))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler",
                         _launch_trap("src.crawler.pipe_scraper.AsyncWebCrawler"))


@pytest.fixture(autouse=True)
def _isolated_tempdir(monkeypatch, tmp_path_factory):
    isolated = tmp_path_factory.mktemp("systmp")
    monkeypatch.setattr(tempfile, "tempdir", str(isolated))


@pytest.fixture(autouse=True)
def _no_real_osascript(monkeypatch):
    real_run = subprocess.run

    def _guarded_run(args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and args[0] == "osascript":
            pytest.fail("real osascript call attempted — this test must mock it before reaching here",
                        pytrace=False)
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", _guarded_run)


@pytest.fixture(autouse=True)
def _constant_system_locale(monkeypatch):
    monkeypatch.setattr(camoufox_scrape, "_resolve_system_locale", lambda: "en-US")


def _launch_trap(qualified_name: str):
    def _trap(*args, **kwargs):
        pytest.fail(
            f"real browser launch attempted via {qualified_name} — this test must mock it before "
            f"reaching here",
            pytrace=False,
        )
    return _trap
