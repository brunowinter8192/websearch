#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pydoll.exceptions as _pydoll_exc
import websockets.exceptions as _ws_exc

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search import status as S
from src.search import status_timeout as ST
from src.search import status_error as SE
from src.search.browser import close_browser
from src.search.engines import duckduckgo as duckduckgo_engine
from src.search.engines import openalex as openalex_engine

from src.search.engines import scholar as scholar_engine

REPORT_DIR = SCRIPT_DIR / "jsonl"

WATCHDOG: dict[str, float] = {
    "google_scholar": 6.0,
}
DEFAULT_WATCHDOG = 3.6

QUERIES = [
    "neural network optimization Adam SGD convergence",
    "transformer architecture vision image classification",
    "BERT fine-tuning downstream tasks benchmark",
    "Tiefes Lernen Convolutional Netze Bilderkennung",
    "quantum computing error correction surface code",
    "reinforcement learning reward shaping sparse signal",
    "federated learning privacy preserving gradient",
    "Sprachmodelle GPT Trainingsdaten Skalierungsgesetze",
    "graph neural network knowledge graph embedding",
    "knowledge distillation teacher student model",
    "continual learning catastrophic forgetting replay",
    "Optimierung Gradientenverfahren neuronale Netzwerke Konvergenz",
]


# ORCHESTRATOR

async def run_smoke() -> None:
    _configure_logging()
    _prepare_report_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = _compute_report_path(ts)

    engines = _compute_engines()

    _print_smoke_9_engines(report_path)
    print(file=sys.stderr)

    records = await _run_burst_queries(engines, report_path)

    _print_summary(records)
    _print_report_written(report_path)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _prepare_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _compute_report_path(ts):
    report_path = REPORT_DIR / f"no_google_burst_{ts}.jsonl"
    return report_path


def _compute_engines():
    engines = {
        "google_scholar": scholar_engine,
        "duckduckgo": duckduckgo_engine,
        "openalex": openalex_engine,
    }
    return engines


def _print_smoke_9_engines(report_path):
    print(f"Smoke: 9 engines (no Google), {len(QUERIES)} queries", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)


async def _run_burst_queries(engines, report_path):
    records = []
    try:
        for qi, query in enumerate(QUERIES):
            burst = qi // 4 + 1
            q_in_burst = qi % 4 + 1
            label = f"B{burst}-Q{q_in_burst}"
            print(f"[{qi + 1:02}/{len(QUERIES)}] {label} {query}", file=sys.stderr)
            record = await _run_burst(engines, query, label)
            records.append(record)
            scholar_status = record["engines"].get("google_scholar", {}).get("status", "?")
            scholar_ms = record["engines"].get("google_scholar", {}).get("search_ms", 0)
            scholar_n = record["engines"].get("google_scholar", {}).get("result_count", 0)
            print(f"         google_scholar={scholar_status} ms={scholar_ms} n={scholar_n}", file=sys.stderr)
            with open(report_path, "a") as f:
                f.write(json.dumps(record) + "\n")
    finally:
        await close_browser()
    return records


def _print_summary(records: list[dict]) -> None:
    print("\n=== SCHOLAR HTTP (PRODUCTION) SUMMARY ===", file=sys.stderr)
    print(f"{'#':3} {'Label':7} {'Scholar status':22} {'ms':6} {'n':4} {'query':45}", file=sys.stderr)
    print("-" * 95, file=sys.stderr)
    scholar_entries = []
    for i, rec in enumerate(records):
        s = rec["engines"].get("google_scholar", {})
        status = s.get("status", "?")
        ms = s.get("search_ms", 0)
        n = s.get("result_count", 0)
        blocked = s.get("blocked", False)
        scholar_entries.append((status, blocked))
        print(f"{i + 1:3} {rec['label']:7} {status:22} {ms:6} {n:4} {rec['query'][:45]}", file=sys.stderr)

    from collections import Counter
    counts = Counter(status for status, _ in scholar_entries)
    effective = [(status, blocked) for status, blocked in scholar_entries if status != S.RATE_SKIP]
    blocks = [blocked for _, blocked in effective if blocked]

    print(file=sys.stderr)
    print("Scholar status distribution:", dict(counts), file=sys.stderr)
    print(f"Effective attempts (non-RATE_SKIP): {len(effective)}/{len(scholar_entries)}", file=sys.stderr)
    block_rate = f"{len(blocks) / len(effective) * 100:.0f}%" if effective else "N/A"
    print(f"Blocked (captcha_form or 30x http_status fact): {len(blocks)}/{len(effective)} effective → block rate {block_rate}", file=sys.stderr)


def _print_report_written(report_path):
    print(f"\nReport written: {report_path}", file=sys.stderr)


async def _run_burst(engines: dict, query: str, label: str) -> dict:
    t_wall = time.perf_counter()
    tasks = {
        name: asyncio.create_task(
            _run_engine(eng, query, WATCHDOG.get(name, DEFAULT_WATCHDOG))
        )
        for name, eng in engines.items()
    }
    results_map = dict(zip(tasks.keys(), await asyncio.gather(*tasks.values(), return_exceptions=True)))
    wall_ms = round((time.perf_counter() - t_wall) * 1000)

    engine_stats = {}
    for name, result in results_map.items():
        if isinstance(result, Exception):
            engine_stats[name] = {"status": "ERROR", "search_ms": 0, "result_count": 0, "error": str(result), "blocked": False}
        else:
            status, search_ms, result_count, blocked = result
            engine_stats[name] = {"status": status, "search_ms": search_ms, "result_count": result_count, "blocked": blocked}

    return {
        "label": label,
        "query": query,
        "wall_ms": wall_ms,
        "engines": engine_stats,
    }


async def _run_engine(engine, query: str, timeout: float) -> tuple[str, int, int, bool]:
    t0 = time.perf_counter()
    try:
        results, reason, diagnosis = await asyncio.wait_for(
            engine.search_with_reason(query, "en", 10),
            timeout=timeout,
        )
        search_ms = round((time.perf_counter() - t0) * 1000)
        blocked = _is_blocked(diagnosis)
        if results:
            return S.OK, search_ms, len(results), blocked
        return reason or S.EMPTY, search_ms, 0, blocked
    except asyncio.TimeoutError:
        search_ms = round((time.perf_counter() - t0) * 1000)
        return ST.TIMEOUT_WATCHDOG, search_ms, 0, False
    except httpx.TimeoutException:
        search_ms = round((time.perf_counter() - t0) * 1000)
        return ST.TIMEOUT_HTTPX, search_ms, 0, False
    except (_pydoll_exc.PydollException, _ws_exc.WebSocketException, ConnectionError):
        search_ms = round((time.perf_counter() - t0) * 1000)
        return SE.ERROR_BROWSER, search_ms, 0, False
    except httpx.HTTPError:
        search_ms = round((time.perf_counter() - t0) * 1000)
        return SE.ERROR_HTTP, search_ms, 0, False
    except Exception:
        search_ms = round((time.perf_counter() - t0) * 1000)
        return "ERROR", search_ms, 0, False


def _is_blocked(diagnosis: dict | None) -> bool:
    if not diagnosis:
        return False
    if diagnosis.get("captcha_form"):
        return True
    status = diagnosis.get("http_status")
    return isinstance(status, int) and 300 <= status < 400


if __name__ == "__main__":
    asyncio.run(run_smoke())
