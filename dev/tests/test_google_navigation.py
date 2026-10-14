# INFRASTRUCTURE
import asyncio

import pytest
from pydoll.exceptions import NavigationError, PageLoadTimeout
from pydoll.protocol.page.events import PageEvent

from src.search import search_web
from src.search.engines import google as google_mod
from src.search.engines.google import GOTO_RESOLVE_TIMEOUT_S, NAVIGATION_TIMEOUT_S, _go_to_dom_content_loaded

SEARCH_URL = "https://www.google.com/search?q=heat+pump&hl=en&num=100"


class _FakeTab:
    def __init__(self, fire_dom_content: bool = True, error_text: str | None = None):
        self.calls: list[str] = []
        self.callbacks: dict[str, object] = {}
        self.fire_dom_content = fire_dom_content
        self.error_text = error_text

    async def enable_page_events(self):
        self.calls.append("enable_page_events")

    async def on(self, event_name, callback):
        self.calls.append(f"on:{event_name}")
        self.callbacks[event_name] = callback
        return len(self.callbacks)

    async def _execute_command(self, command):
        self.calls.append(f"command:{command['method'].value}")
        if self.fire_dom_content:
            self.callbacks[PageEvent.DOM_CONTENT_EVENT_FIRED]({})
        result = {"errorText": self.error_text} if self.error_text else {}
        return {"result": result}


# FUNCTIONS

def test_navigation_returns_at_dom_content_loaded_without_a_load_event():
    tab = _FakeTab(fire_dom_content=True)

    asyncio.run(_go_to_dom_content_loaded(tab, SEARCH_URL, timeout=1.0))

    assert PageEvent.LOAD_EVENT_FIRED not in tab.callbacks


def test_listener_is_registered_before_the_navigate_command():
    tab = _FakeTab()

    asyncio.run(_go_to_dom_content_loaded(tab, SEARCH_URL, timeout=1.0))

    assert tab.calls == ["enable_page_events", f"on:{PageEvent.DOM_CONTENT_EVENT_FIRED}", "command:Page.navigate"]


def test_missing_dom_content_event_raises_page_load_timeout_after_one_bounded_wait():
    tab = _FakeTab(fire_dom_content=False)

    with pytest.raises(PageLoadTimeout):
        asyncio.run(_go_to_dom_content_loaded(tab, SEARCH_URL, timeout=0.05))

    assert tab.calls.count("command:Page.navigate") == 1


def test_navigate_error_text_raises_navigation_error():
    tab = _FakeTab(fire_dom_content=False, error_text="net::ERR_CONNECTION_REFUSED")

    with pytest.raises(NavigationError):
        asyncio.run(_go_to_dom_content_loaded(tab, SEARCH_URL, timeout=1.0))


def test_search_in_tab_navigates_with_the_dom_content_helper_and_the_navigation_timeout(monkeypatch):
    seen = {}

    async def _fake_capture(tab):
        return []

    async def _fake_navigation(tab, url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        raise PageLoadTimeout()

    monkeypatch.setattr(google_mod, "start_document_status_capture", _fake_capture)
    monkeypatch.setattr(google_mod, "_go_to_dom_content_loaded", _fake_navigation)

    with pytest.raises(PageLoadTimeout):
        asyncio.run(google_mod._search_in_tab(object(), "heat pump", 100, None, 0.0, SEARCH_URL))

    assert seen == {"url": SEARCH_URL, "timeout": NAVIGATION_TIMEOUT_S}


def test_navigation_plus_url_resolution_fits_the_engine_watchdog():
    assert NAVIGATION_TIMEOUT_S + GOTO_RESOLVE_TIMEOUT_S < search_web.ENGINE_WATCHDOG_TIMEOUT
