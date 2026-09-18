# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import pydoll.exceptions as _pydoll_exc
import websockets.exceptions as _ws_exc
from mcp.types import TextContent

from src.search.browser import get_tab, kill_own_chrome
from src.search.cache import cache_key, cache_write
from src.search.engines.google import GoogleEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.mojeek import MojeekEngine
from src.search.engines.startpage import StartpageEngine
from src.search.engines.brave import BraveEngine
from src.search.engines.bing import BingEngine
from src.search.engines.yandex import YandexEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.rate_limiter import get_limiter
from src.search.result import SearchResult
from src.search.merge import build_engine_pools
from src.search import status as S
from src.search import status_timeout as ST
from src.search import status_error as SE
from src.search.query_logger import log_query

logger = logging.getLogger(__name__)

_DEFAULT_ENGINES: frozenset[str] = frozenset({
    "google", "duckduckgo", "mojeek",
    "openalex", "startpage", "brave", "bing", "yandex",
})

_BROWSER_ENGINES: frozenset[str] = frozenset({
    "google", "duckduckgo", "mojeek",
    "startpage", "brave", "bing", "yandex",
})

ENGINE_WATCHDOG_TIMEOUT: float = 6.0
RATE_WAIT_TIMEOUT: float = 60.0
POOL_CAP: int = 10

ENGINE_MAX_RESULTS: dict[str, int] = {
    "google": 100,
    "duckduckgo": 10,
    "mojeek": 10,
    "openalex": 100,
    "startpage": 10,
    "brave": 10,
    "bing": 10,
    "yandex": 10,
}

ENGINES = {
    "google": GoogleEngine(),
    "duckduckgo": DuckDuckGoEngine(),
    "mojeek": MojeekEngine(),
    "openalex": OpenAlexEngine(),
    "startpage": StartpageEngine(),
    "brave": BraveEngine(),
    "bing": BingEngine(),
    "yandex": YandexEngine(),
}

# ORCHESTRATOR

async def search_web_workflow(
    query: str,
    language: str = "en",
    time_range: str | None = None,
    engines: str | None = None,
    _with_timings: bool = False,
    engine_timeout: float | None = None,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
) -> list[TextContent] | tuple[list[TextContent], dict]:
    t_total = time.perf_counter()
    logger.info("Searching: %s (language=%s)", query, language)
    selected, all_excluded = _select_engines(engines)
    effective_timeout = engine_timeout if engine_timeout is not None else ENGINE_WATCHDOG_TIMEOUT

    try:
        if _BROWSER_ENGINES & selected.keys():
            await _prewarm_browser()
        raw_results, engine_stats, engine_fanout_ms, engine_ms, engine_details = await _run_engine_fanout(
            selected, query, language, effective_timeout, query_modifier_map, _with_timings
        )
    finally:
        await kill_own_chrome()

    t0 = time.perf_counter()
    pools = build_engine_pools(raw_results)
    pool_build_ms = round((time.perf_counter() - t0) * 1000)

    capped_pools = _cap_pools(pools)

    formatted_text = _format_breakdown(query, capped_pools, list(selected.keys()))

    key = cache_key(query, language, engines, time_range)
    t0 = time.perf_counter()
    cache_write(key, capped_pools, query, language, engines, time_range)
    cache_write_ms = round((time.perf_counter() - t0) * 1000)

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _build_query_log_entry(query, language, selected, total_ms, engine_stats, all_excluded, key)

    return _build_search_result(
        formatted_text, _with_timings, engine_fanout_ms, engine_ms, engine_details,
        pool_build_ms, cache_write_ms, total_ms,
    )


def fetch_search_results(
    query: str,
    category: str,
    language: str,
    time_range: str | None,
    engines: str | None,
    pageno: int
) -> list:
    selected, _ = _select_engines(engines)
    results, _ = asyncio.run(_query_engines_concurrent(query, language, 10, selected))
    return [
        {
            "url": r.url,
            "title": r.title,
            "content": r.snippet,
            "engines": [r.engine],
        }
        for r in results
    ]


# FUNCTIONS

async def _prewarm_browser() -> None:
    try:
        await get_tab()
    except Exception as e:
        logger.warning("Browser prewarm failed, engines will retry individually: %s", e)


def _cap_pools(pools: dict) -> dict:
    logger.info("Pool cap applied: %d", POOL_CAP)
    return {eng: pool[:POOL_CAP] for eng, pool in pools.items()}


def _build_search_result(
    formatted_text: str,
    with_timings: bool,
    engine_fanout_ms: int,
    engine_ms: dict,
    engine_details: dict,
    pool_build_ms: int,
    cache_write_ms: int,
    total_ms: int,
) -> list[TextContent] | tuple[list[TextContent], dict]:
    result = [TextContent(type="text", text=formatted_text)]
    if not with_timings:
        return result
    timings = {
        "engine_fanout_ms": engine_fanout_ms,
        **engine_ms,
        "engine_details": engine_details,
        "pool_build_ms": pool_build_ms,
        "cache_write_ms": cache_write_ms,
        "total_ms": total_ms,
    }
    return result, timings


def _select_engines(engines: str | None) -> tuple[dict, dict[str, str]]:
    if not engines:
        selected = {k: v for k, v in ENGINES.items() if k in _DEFAULT_ENGINES}
        return selected, {}
    names = [e.strip().lower() for e in engines.split(",")]
    return {k: v for k, v in ENGINES.items() if k in names}, {}


async def _run_engine_fanout(
    selected: dict,
    query: str,
    language: str,
    effective_timeout: float,
    query_modifier_map: dict[str, Callable] | None,
    with_timings: bool,
) -> tuple[list, dict, int, dict, dict]:
    raw_results: list = []
    engine_ms: dict[str, int] = {}
    engine_stats: dict[str, dict] = {}
    t_fanout = time.perf_counter()
    if with_timings:
        names_and_engines = list(selected.items())
        tasks = [
            _engine_with_timing(eng, query, language, 10, effective_timeout, query_modifier_map=query_modifier_map)
            for _, eng in names_and_engines
        ]
        timed = await asyncio.gather(*tasks)
        engine_details: dict[str, dict] = {}
        for (name, eng), (eng_results, rate_wait_ms, search_ms, status, drop_reason, diagnosis) in zip(names_and_engines, timed):
            raw_results.extend(eng_results)
            key = name.replace(' ', '_')
            engine_ms[f"engine_{key}_ms"] = search_ms
            engine_details[key] = {"status": status, "ms": search_ms}
            engine_stats[eng.name] = {
                "rate_wait_ms": rate_wait_ms,
                "search_ms": search_ms,
                "status": status,
                "result_count": len(eng_results),
                "drop_reason": drop_reason,
                "diagnosis": diagnosis,
            }
    else:
        raw_results, engine_stats = await _query_engines_concurrent(
            query, language, 10, selected, query_modifier_map=query_modifier_map
        )
        engine_details = {}
    engine_fanout_ms = round((time.perf_counter() - t_fanout) * 1000)
    return raw_results, engine_stats, engine_fanout_ms, engine_ms, engine_details


async def _query_engines_concurrent(
    query: str,
    language: str,
    max_results: int,
    selected: dict,
    timeout: float = ENGINE_WATCHDOG_TIMEOUT,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
) -> tuple[list, dict[str, dict]]:
    tasks = [
        _engine_with_timing(engine, query, language, max_results, timeout, query_modifier_map=query_modifier_map)
        for engine in selected.values()
    ]
    timed = await asyncio.gather(*tasks)
    combined: list = []
    engine_stats: dict[str, dict] = {}
    for engine, (eng_results, rate_wait_ms, search_ms, status, drop_reason, diagnosis) in zip(selected.values(), timed):
        combined.extend(eng_results)
        engine_stats[engine.name] = {
            "rate_wait_ms": rate_wait_ms,
            "search_ms": search_ms,
            "status": status,
            "result_count": len(eng_results),
            "drop_reason": drop_reason,
            "diagnosis": diagnosis,
        }
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log_query({
        "record_type": "engine_run",
        "ts": ts,
        "query": query,
        "language": language,
        "engines_requested": list(selected.keys()),
        "engines": engine_stats,
    })
    return combined, engine_stats


def _classify_engine_exception(exc: Exception, timeout: float | None, search_ms: int) -> tuple[str, str]:
    if isinstance(exc, asyncio.TimeoutError):
        sub = ST.TIMEOUT_WATCHDOG if timeout is not None and search_ms < timeout * 1.2 * 1000 else ST.TIMEOUT_NONCOOP
        return sub, f"asyncio.TimeoutError after {timeout}s watchdog"
    if isinstance(exc, httpx.TimeoutException):
        logger.warning("Engine httpx timeout: %s", exc)
        return ST.TIMEOUT_HTTPX, str(exc)
    if isinstance(exc, (_pydoll_exc.PydollException, _ws_exc.WebSocketException, ConnectionError)):
        logger.warning("Engine browser error: %s", exc)
        return SE.ERROR_BROWSER, str(exc)
    if isinstance(exc, httpx.HTTPError):
        logger.warning("Engine HTTP error: %s", exc)
        return SE.ERROR_HTTP, str(exc)
    if isinstance(exc, (json.JSONDecodeError, KeyError, ValueError, AttributeError)):
        logger.warning("Engine parse error: %s", exc)
        return SE.ERROR_PARSE, str(exc)
    logger.warning("Engine error: %s", exc)
    return SE.ERROR_OTHER, str(exc)


async def _engine_with_timing(
    engine,
    query: str,
    language: str,
    max_results: int,
    timeout: float | None = None,
    query_modifier_map: dict[str, Callable[[str], str]] | None = None,
) -> tuple[list, int, int, str, str | None, dict | None]:
    t_before_acquire = time.perf_counter()
    try:
        await asyncio.wait_for(get_limiter(engine.name).acquire(), timeout=RATE_WAIT_TIMEOUT)
    except asyncio.TimeoutError:
        rate_wait_ms = round((time.perf_counter() - t_before_acquire) * 1000)
        return [], rate_wait_ms, 0, S.RATE_SKIP, f"rate_wait > {RATE_WAIT_TIMEOUT}s", None
    rate_wait_ms = round((time.perf_counter() - t_before_acquire) * 1000)
    effective_query = query
    if query_modifier_map and engine.name in query_modifier_map:
        effective_query = query_modifier_map[engine.name](query)
    logger.debug("Engine %s effective_query: %s", engine.name, effective_query)
    effective_max = ENGINE_MAX_RESULTS.get(engine.name, max_results)
    t0 = time.perf_counter()
    try:
        if timeout is not None:
            results, empty_reason, diagnosis = await asyncio.wait_for(engine.search_with_reason(effective_query, language, effective_max), timeout=timeout)
        else:
            results, empty_reason, diagnosis = await engine.search_with_reason(effective_query, language, effective_max)
        search_ms = round((time.perf_counter() - t0) * 1000)
        if results:
            return results, rate_wait_ms, search_ms, S.OK, None, diagnosis
        return [], rate_wait_ms, search_ms, empty_reason or S.EMPTY, None, diagnosis
    except Exception as e:
        search_ms = round((time.perf_counter() - t0) * 1000)
        status, drop_reason = _classify_engine_exception(e, timeout, search_ms)
        return [], rate_wait_ms, search_ms, status, drop_reason, None


def _format_breakdown(query: str, pools: dict[str, list[SearchResult]], all_engine_names: list[str]) -> str:
    lines = [f'Engine breakdown for "{query}":']
    for engine in all_engine_names:
        count = len(pools.get(engine, []))
        lines.append(f"  {engine:<20} {count}")
    lines.append("")
    lines.append(f'Use `websearch search_engine_drilldown "{query}" --engine <name>` to see URLs per engine.')
    return "\n".join(lines)


def _build_query_log_entry(
    query: str,
    language: str,
    selected: dict,
    total_ms: int,
    engine_stats: dict,
    engines_excluded: dict[str, str],
    search_key: str,
) -> None:
    bottleneck = max(engine_stats, key=lambda k: engine_stats[k]["search_ms"]) if engine_stats else None
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log_query({
        "record_type": "workflow_summary",
        "ts": ts,
        "query": query,
        "language": language,
        "engines_requested": [eng.name for eng in selected.values()],
        "engines_excluded": engines_excluded,
        "total_wall_ms": total_ms,
        "bottleneck_engine": bottleneck,
        "engines": engine_stats,
        "search_key": search_key,
    })
