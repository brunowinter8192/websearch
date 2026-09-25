# INFRASTRUCTURE
import json

import pytest

from src.search.engines import bing, brave, google, yandex
from src.search.selector_hits import collect_selector_hits

ENGINE_ITEMS = {
    google: {"url": "https://www.google.com/goto?url=a", "title": "T", "snippet": "S", "date": None},
    bing: {"url": "https://e.test/a", "title": "T", "snippet": "S", "date_raw": ""},
    brave: {"url": "https://e.test/a", "title": "T", "snippet": "S"},
    yandex: {"url": "https://e.test/a", "title": "T", "snippet": "S"},
}


# FUNCTIONS

def test_collect_selector_hits_counts_per_field_and_index():
    items = [{"sel": {"anchor": 0, "snippet": 1}}, {"sel": {"anchor": 0}}, {"sel": {}}, {}]
    assert collect_selector_hits(items) == {"anchor": {"0": 2}, "snippet": {"1": 1}}


def test_collect_selector_hits_empty():
    assert collect_selector_hits([]) == {}


@pytest.mark.parametrize("module", list(ENGINE_ITEMS), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_sel_key_never_reaches_the_results(module):
    item = ENGINE_ITEMS[module]
    plain = module._build_results([item], 10)
    with_sel = module._build_results([{**item, "sel": {"snippet": 1}}], 10)
    assert plain == with_sel


@pytest.mark.asyncio
@pytest.mark.parametrize("module", list(ENGINE_ITEMS), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
async def test_parse_results_returns_results_and_hits(module):
    items = [{**ENGINE_ITEMS[module], "sel": {"snippet": 0}}, {**ENGINE_ITEMS[module], "url": ENGINE_ITEMS[module]["url"] + "2", "sel": {"snippet": 1}}]
    results, hits = await module._parse_results(_Tab(json.dumps(items)), 10)
    assert len(results) == 2
    assert hits == {"snippet": {"0": 1, "1": 1}}


@pytest.mark.asyncio
@pytest.mark.parametrize("module", list(ENGINE_ITEMS), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
async def test_parse_results_hits_only_count_items_within_max_results(module):
    items = [{**ENGINE_ITEMS[module], "url": ENGINE_ITEMS[module]["url"] + str(i), "sel": {"snippet": i}} for i in range(3)]
    _, hits = await module._parse_results(_Tab(json.dumps(items)), 2)
    assert hits == {"snippet": {"0": 1, "1": 1}}


@pytest.mark.asyncio
@pytest.mark.parametrize("module", list(ENGINE_ITEMS), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
async def test_parse_results_empty_value_yields_empty_hits(module):
    assert await module._parse_results(_Tab(None), 10) == ([], {})


def test_google_consent_branch_is_gone():
    assert not hasattr(google, "_has_inline_consent")
    assert not hasattr(google, "_handle_consent")
    assert not hasattr(google, "_JS_CONSENT")
    assert not hasattr(google, "CONSENT_DOMAIN")


class _Tab:
    def __init__(self, value):
        self._value = value

    async def execute_script(self, script):
        return {"result": {"result": {"value": self._value}}}
