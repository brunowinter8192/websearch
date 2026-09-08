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

# From browser.py: deterministic own-browser teardown, called in a finally around the engine sweep
from src.search.browser import get_tab, kill_own_chrome
from src.search.cache import cache_key, cache_write
from src.search.engines.google import GoogleEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.startpage import StartpageEngine
from src.search.engines.brave import BraveEngine
from src.search.engines.bing import BingEngine
from src.search.engines.yandex import YandexEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.rate_limiter import get_limiter
from src.search.result import SearchResult
# From merge.py: per-engine pool builder with cross-engine URL dedup
from src.search.merge import build_engine_pools
# From status.py: sub-status string constants
from src.search import status as S
# From query_logger.py: append-only JSONL query log
from src.search.query_logger import log_query

logger = logging.getLogger(__name__)

_DEFAULT_ENGINES: frozenset[str] = frozenset({
    "google", "duckduckgo",
    "openalex", "startpage", "brave", "bing", "yandex",
})

# Engines that share the pydoll Chrome session (browser.py) — the only ones _prewarm_browser
# needs to launch for
_BROWSER_ENGINES: frozenset[str] = frozenset({
    "google", "duckduckgo",
    "startpage", "brave", "bing", "yandex",
})

# Uniform across all engines (2026-08-25) — a per-engine override (3.6s default, up to 6.0s for
# open_library/semantic_scholar/crossref/startpage/brave) saved no wall time since engines run
# concurrently and the sweep already paid the 6.0s class on nearly every run (138 workflow_summary
# records: bottleneck semantic_scholar 84x/startpage 26x/open_library 19x, google only 3x), while
# censoring slow-yet-alive engines at the shorter 3.6s (google 19x TIMEOUT_WATCHDOG, duckduckgo 46x).
ENGINE_WATCHDOG_TIMEOUT: float = 6.0
RATE_WAIT_TIMEOUT: float = 60.0

ENGINE_MAX_RESULTS: dict[str, int] = {
    "google": 100,
    "duckduckgo": 10,
    "openalex": 100,
    "startpage": 10,
    "brave": 10,
    "bing": 10,
    "yandex": 10,
}

ENGINES = {
    "google": GoogleEngine(),
    "duckduckgo": DuckDuckGoEngine(),
    "openalex": OpenAlexEngine(),
    "startpage": StartpageEngine(),
    "brave": BraveEngine(),
    "bing": BingEngine(),
    "yandex": YandexEngine(),
}

# ORCHESTRATOR

# Fan out to all enabled engines, build per-engine pools, format breakdown table, cache, log, return TextContent
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


# Synchronous wrapper for dev scripts — runs event loop internally
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

# Launch (or reuse) the shared browser OUTSIDE any per-engine watchdog — a per-engine timeout
# (3.6-6.0s) is far shorter than a legitimate cross-process lock wait, so doing this lazily inside
# an engine's own asyncio.wait_for-guarded call let the watchdog cancel get_tab() mid-wait,
# abandoning its blocking lock-acquire thread and letting the next engine retry from scratch
# (caught live via a two-parallel-CLI-run test). A real launch failure here is swallowed and
# re-surfaces identically per-engine when their own new_tab() call retries it.
async def _prewarm_browser() -> None:
    try:
        await get_tab()
    except Exception as e:
        logger.warning("Browser prewarm failed, engines will retry individually: %s", e)


# Cap each engine's pool to K = google's pool size (fallback 10) — prevents drilldown floods
def _cap_pools(pools: dict) -> dict:
    google_count = len(pools.get("google", []))
    K = google_count if google_count > 0 else 10
    logger.info("Pool cap K=%d (google_count=%d)", K, google_count)
    return {eng: pool[:K] for eng, pool in pools.items()}


# Build the workflow's return value — plain [TextContent], or with _with_timings, (result, timings_dict)
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


# Filter engine registry; return (selected, excluded) — excluded maps engine.name to reason for engines not included
def _select_engines(engines: str | None) -> tuple[dict, dict[str, str]]:
    if not engines:
        selected = {k: v for k, v in ENGINES.items() if k in _DEFAULT_ENGINES}
        return selected, {}
    names = [e.strip().lower() for e in engines.split(",")]
    return {k: v for k, v in ENGINES.items() if k in names}, {}


# Execute engine fanout (timed or plain); return (raw_results, engine_stats, fanout_ms, engine_ms, engine_details)
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


# Query selected engines concurrently; write engine_run log entry; return (combined_results, engine_stats_dict)
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


# Map an engine-search exception to (status, drop_reason) — same match order as the original except chain
def _classify_engine_exception(exc: Exception, timeout: float | None, search_ms: int) -> tuple[str, str]:
    if isinstance(exc, asyncio.TimeoutError):
        sub = S.TIMEOUT_WATCHDOG if timeout is not None and search_ms < timeout * 1.2 * 1000 else S.TIMEOUT_NONCOOP
        return sub, f"asyncio.TimeoutError after {timeout}s watchdog"
    if isinstance(exc, httpx.TimeoutException):
        logger.warning("Engine httpx timeout: %s", exc)
        return S.TIMEOUT_HTTPX, str(exc)
    if isinstance(exc, (_pydoll_exc.PydollException, _ws_exc.WebSocketException, ConnectionError)):
        logger.warning("Engine browser error: %s", exc)
        return S.ERROR_BROWSER, str(exc)
    if isinstance(exc, httpx.HTTPError):
        logger.warning("Engine HTTP error: %s", exc)
        return S.ERROR_HTTP, str(exc)
    if isinstance(exc, (json.JSONDecodeError, KeyError, ValueError, AttributeError)):
        logger.warning("Engine parse error: %s", exc)
        return S.ERROR_PARSE, str(exc)
    logger.warning("Engine error: %s", exc)
    return S.ERROR_OTHER, str(exc)


# Wrap single engine search; return (results, rate_wait_ms, search_ms, status, drop_reason, diagnosis) —
# diagnosis is the raw-facts snapshot behind a non-None empty_reason (browser engines), or None
# (success, or engines with no diagnosis mechanism: openalex, scholar)
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


# Format per-engine result counts as a breakdown table with drilldown hint
def _format_breakdown(query: str, pools: dict[str, list[SearchResult]], all_engine_names: list[str]) -> str:
    lines = [f'Engine breakdown for "{query}":']
    for engine in all_engine_names:
        count = len(pools.get(engine, []))
        lines.append(f"  {engine:<20} {count}")
    lines.append("")
    lines.append(f'Use `websearch search_engine_drilldown "{query}" --engine <name>` to see URLs per engine.')
    return "\n".join(lines)


# Build and write workflow_summary log entry after each search_web_workflow call
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
