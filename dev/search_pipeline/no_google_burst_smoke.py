#!/usr/bin/env python3
"""
No-Google concurrent burst smoke — production ScholarEngine vs 8 production engines.

Architectural discriminator test: does HTTP Scholar survive the concurrent multi-engine
burst pattern when Google browser is absent?

Engine set (9 total, no Google):
  google_scholar (production HTTP), duckduckgo, mojeek, lobsters, crossref, openalex,
  stack_exchange, semantic_scholar, open_library

Queries: 12 canonical academic queries from ciw_concurrent_block_20260508.md
(3 bursts × 4), reused for cross-test comparability.

Import switched from ScholarHTTPProbe (dev probe) to ScholarEngine (production) 2026-05-09
as part of bead searxng-f3i HTTP migration.

Output: JSONL per-query records → dev/search_pipeline/jsonl/no_google_burst_<ts>.jsonl
        Summary table → stderr
"""

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
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.openalex import OpenAlexEngine

from src.search.engines.scholar import ScholarEngine

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "jsonl"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Watchdog timeouts per engine (seconds) — this probe's own values, independent of
# search_web.py's ENGINE_WATCHDOG_TIMEOUT (uniform 6.0s across all engines as of 2026-08-25)
WATCHDOG: dict[str, float] = {
    "google_scholar": 6.0,
}
DEFAULT_WATCHDOG = 3.6

# 12 canonical queries — 3 bursts × 4, identical to ciw_concurrent_block_20260508.md
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
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"no_google_burst_{ts}.jsonl"

    engines = {
        "google_scholar": ScholarEngine(),
        "duckduckgo": DuckDuckGoEngine(),
        "openalex": OpenAlexEngine(),
    }

    print(f"Smoke: 9 engines (no Google), {len(QUERIES)} queries", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(file=sys.stderr)

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

    _print_summary(records)
    print(f"\nReport written: {report_path}", file=sys.stderr)


# FUNCTIONS

# Run all 9 engines concurrently for one query; return per-engine stats dict
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


# A block observed as a FACT from scholar's diagnosis snapshot — the inline captcha-form element's
# presence, or a 30x redirect status — never the removed EMPTY_BLOCK verdict this metric used to
# key on. Applies to any engine's diagnosis shape that carries these two fields; scholar is the
# only one in this probe's engine set that ever populates them.
def _is_blocked(diagnosis: dict | None) -> bool:
    if not diagnosis:
        return False
    if diagnosis.get("captcha_form"):
        return True
    status = diagnosis.get("http_status")
    return isinstance(status, int) and 300 <= status < 400


# Drive one engine with watchdog timeout; return (status, search_ms, result_count, blocked)
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


# Print per-query Scholar status table + aggregate to stderr
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
    # Block rate keyed on the FACT (scholar's diagnosis: captcha_form present, or a 30x http_status)
    # instead of the removed EMPTY_BLOCK verdict — this metric is the probe's whole purpose, and
    # search_with_reason's diagnosis dict is directly in hand here (unlike acquire_probe.py/
    # branch_probe.py/cdp_starvation_probe.py, which only see status through engine_details).
    blocks = [blocked for _, blocked in effective if blocked]

    print(file=sys.stderr)
    print("Scholar status distribution:", dict(counts), file=sys.stderr)
    print(f"Effective attempts (non-RATE_SKIP): {len(effective)}/{len(scholar_entries)}", file=sys.stderr)
    block_rate = f"{len(blocks) / len(effective) * 100:.0f}%" if effective else "N/A"
    print(f"Blocked (captcha_form or 30x http_status fact): {len(blocks)}/{len(effective)} effective → block rate {block_rate}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_smoke())
