#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from _date_availability_probe_browser import _extract_value, _kill_tab, _new_tab, close_browser
from _date_availability_probe_nav import CONTAINER_SELECTOR, NAV_FUNCS
from _date_availability_probe_report import write_report

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent.parent
REPORT_DIR = SCRIPT_DIR / "md"

INTER_QUERY_DELAY_S = 20.0
INTER_ENGINE_DELAY_S = 3.0
RETRY_COOLDOWN_S = 180.0

CONTAINER_LIMIT = 3

QUERIES = [
    ("openai gpt-5 release reaction", "news-en"),
    ("federal reserve interest rate decision 2026", "news-en"),
    ("Photosynthese Prozess pflanzliche Zellatmung", "reference-de"),
]


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        for engine in CONTAINER_SELECTOR:
            print(f"=== {engine} ===", file=sys.stderr)
            engine_records = []
            for qi, (query, axis) in enumerate(QUERIES):
                print(f"  [{qi + 1}/{len(QUERIES)}] ({axis}) {query}", file=sys.stderr)
                rec = await run_engine_query(engine, query, axis, retry=False)
                engine_records.append(rec)
                print(f"    -> {rec['status']} containers={rec['container_count']}", file=sys.stderr)
                if qi < len(QUERIES) - 1:
                    await asyncio.sleep(INTER_QUERY_DELAY_S)
            if all(r["status"] != "OK" for r in engine_records):
                print(f"  all {len(QUERIES)} primary queries non-OK — cooling down {RETRY_COOLDOWN_S:.0f}s before retry", file=sys.stderr)
                await asyncio.sleep(RETRY_COOLDOWN_S)
                retry_rec = await run_engine_query(engine, QUERIES[0][0], QUERIES[0][1], retry=True)
                print(f"    retry -> {retry_rec['status']} containers={retry_rec['container_count']}", file=sys.stderr)
                engine_records.append(retry_rec)
            records.extend(engine_records)
            await asyncio.sleep(INTER_ENGINE_DELAY_S)
    finally:
        await close_browser()

    report_path = write_report(records, REPORT_DIR, QUERIES, RETRY_COOLDOWN_S)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

def _build_date_dump_js(container_selector: str, limit: int) -> str:
    escaped = container_selector.replace("'", "\\'")
    return f"""
var _cs = document.querySelectorAll('{escaped}');
var _out = [];
var _n = Math.min(_cs.length, {limit});
var _rx = /(^|[-_\\s])(date|time|age|publish(ed)?|when|ago)([-_\\s]|$)/i;
for (var _i = 0; _i < _n; _i++) {{
    var _c = _cs[_i];
    var _timeEls = _c.querySelectorAll('time');
    var _times = [];
    for (var _t = 0; _t < _timeEls.length; _t++) {{
        _times.push({{datetime: _timeEls[_t].getAttribute('datetime') || '', text: _timeEls[_t].textContent.trim()}});
    }}
    var _cand = _c.querySelectorAll('[class],[id]');
    var _hits = [];
    for (var _d = 0; _d < _cand.length; _d++) {{
        var _el = _cand[_d];
        var _cls = (_el.className || '').toString();
        var _id = _el.id || '';
        if (_rx.test(_cls) || _rx.test(_id)) {{
            _hits.push({{tag: _el.tagName.toLowerCase(), cls: _cls.slice(0, 80), id: _id.slice(0, 40), text: (_el.textContent || '').trim().slice(0, 150)}});
        }}
    }}
    var _text = (_c.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 600);
    _out.push({{
        time_els: _times,
        date_like_els: _hits.slice(0, 10),
        text: _text,
        html_head: _c.outerHTML.slice(0, 3000)
    }});
}}
return JSON.stringify({{count: _cs.length, samples: _out}});
"""


async def _dump_date_evidence(tab, engine: str) -> dict:
    js = _build_date_dump_js(CONTAINER_SELECTOR[engine], CONTAINER_LIMIT)
    val = _extract_value(await tab.execute_script(js))
    if not val:
        return {"count": 0, "samples": []}
    return json.loads(val)


async def run_engine_query(engine: str, query: str, axis: str, retry: bool) -> dict:
    record: dict = {
        "engine": engine, "query": query, "axis": axis, "retry": retry,
        "status": "EMPTY", "diag": None, "container_count": 0, "samples": [],
    }
    tab = await _new_tab()
    t0 = time.monotonic()
    try:
        ok, diag = await NAV_FUNCS[engine](tab, query)
        if ok:
            evidence = await _dump_date_evidence(tab, engine)
            record["container_count"] = evidence["count"]
            record["samples"] = evidence["samples"]
            record["status"] = "OK" if evidence["count"] > 0 else "EMPTY"
        else:
            record["diag"] = diag
            record["status"] = "BLOCKED" if (diag or {}).get("marker") else "EMPTY"
    except Exception as e:
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        await _kill_tab(tab)
    return record


if __name__ == "__main__":
    asyncio.run(run_probe())
