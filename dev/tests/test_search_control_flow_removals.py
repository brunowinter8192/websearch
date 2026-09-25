import json
import logging
from types import SimpleNamespace

import pytest

import src.search.cache as cache_mod
import src.search.engines.bing as bing_mod
import src.search.engines.brave as brave_mod
import src.search.engines.duckduckgo as duckduckgo_mod
import src.search.engines.google as google_mod
import src.search.engines.mojeek as mojeek_mod
import src.search.engines.startpage as startpage_mod
import src.search.engines.yandex as yandex_mod
import src.search.search_web as search_web
from src.search import status_error as SE
from src.search.cdp_value import extract_value

ENGINE_MODULES = [google_mod, bing_mod, brave_mod, duckduckgo_mod, mojeek_mod, startpage_mod, yandex_mod]
ENGINE_IDS = [m.__name__.rsplit(".", 1)[-1] for m in ENGINE_MODULES]

DIAGNOSE_CALLS = [
    (google_mod, lambda tab: google_mod._diagnose(tab)),
    (bing_mod, lambda tab: bing_mod._diagnose(tab)),
    (brave_mod, lambda tab: brave_mod._diagnose(tab)),
    (duckduckgo_mod, lambda tab: duckduckgo_mod._diagnose(tab)),
    (mojeek_mod, lambda tab: mojeek_mod._diagnose(tab, {})),
    (startpage_mod, lambda tab: startpage_mod._diagnose(tab)),
    (yandex_mod, lambda tab: yandex_mod._diagnose(tab)),
]


class _TabReturning:
    def __init__(self, value):
        self.value = value

    async def execute_script(self, script):
        return {"result": {"result": {"value": self.value}}}


class _Limiter:
    async def acquire(self):
        return None


def test_extract_value_raises_when_the_cdp_result_has_no_value():
    with pytest.raises(KeyError):
        extract_value({"result": {"result": {}}})


def test_extract_value_raises_on_a_non_dict_result():
    with pytest.raises(TypeError):
        extract_value(None)


@pytest.mark.parametrize("module,call", DIAGNOSE_CALLS, ids=ENGINE_IDS)
@pytest.mark.asyncio
async def test_diagnose_raises_on_unparseable_json(module, call):
    with pytest.raises(json.JSONDecodeError):
        await call(_TabReturning("not json{"))


@pytest.mark.asyncio
async def test_brave_poll_state_raises_on_unparseable_json():
    with pytest.raises(json.JSONDecodeError):
        await brave_mod._poll_state(_TabReturning("not json{"))


@pytest.mark.asyncio
async def test_brave_click_challenge_button_raises_on_unparseable_json():
    with pytest.raises(json.JSONDecodeError):
        await brave_mod._click_challenge_button(_TabReturning("not json{"))


def test_cache_read_raises_on_a_corrupt_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    key = "corruptkey"
    (tmp_path / f"{key}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        cache_mod.cache_read(key)


def test_cache_read_still_returns_none_for_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    assert cache_mod.cache_read("absent") is None


@pytest.mark.parametrize("exc", [KeyError("value"), json.JSONDecodeError("bad", "x", 0)], ids=["keyerror", "jsondecode"])
@pytest.mark.asyncio
async def test_propagated_parse_failure_surfaces_as_error_parse_status(monkeypatch, exc):
    monkeypatch.setattr(search_web, "get_limiter", lambda name: _Limiter())

    async def raising(query, language, max_results, partial):
        raise exc

    engine = SimpleNamespace(name="fake", search_with_reason=raising)
    results, _, _, status, drop_reason, _ = await search_web._engine_with_timing(engine, "q", "en", 10, timeout=5.0)
    assert results == []
    assert status == SE.ERROR_PARSE
    assert drop_reason


@pytest.mark.asyncio
async def test_prewarm_failure_log_does_not_claim_a_retry(monkeypatch, caplog):
    async def failing_get_tab():
        raise RuntimeError("DevToolsActivePort did not appear")

    monkeypatch.setattr(search_web, "get_tab", failing_get_tab)
    with caplog.at_level(logging.WARNING, logger=search_web.logger.name):
        await search_web._prewarm_browser()
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 1
    assert "retry" not in messages[0].lower()
    assert "expected to fail individually" in messages[0]
    assert "DevToolsActivePort did not appear" in messages[0]
