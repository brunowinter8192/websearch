# INFRASTRUCTURE
import argparse
import asyncio
import json
import os
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pydoll.protocol.network.events import NetworkEvent
from pydoll.protocol.network.types import ResourceType
from pydoll.protocol.page.events import PageEvent

from dev.kvp.kvp_config import CANARY_JSON_DIR, REPORT_DIR
from src.cdp_value import extract_value
from src.search import search_web
from src.search.document_status import start_document_status_capture
from src.search.engines import google

QUERIES = [
    "how does a heat pump work in winter", "python dataclass vs namedtuple", "best hiking trails black forest",
    "sourdough starter feeding schedule", "kubernetes pod pending reason", "how to remove rust from cast iron",
    "european central bank interest rate decision", "typescript generic constraints explained",
    "marathon training plan 16 weeks", "difference between ssd and nvme", "how to prune apple trees",
    "postgres index only scan", "history of the hanseatic league", "electric car charging cost per kwh",
    "css grid vs flexbox", "how to descale an espresso machine", "rust borrow checker lifetimes",
    "safe temperature for cooked chicken", "tax deductible home office germany", "docker multi stage build size",
    "causes of the french revolution", "how to fix a leaking tap", "machine learning cross validation",
    "best time to visit lisbon", "linux file permissions chmod", "how do vaccines train the immune system",
    "photovoltaic payback period germany", "git rebase vs merge", "how to repot a monstera", "tcp congestion control algorithms",
]
SPACING_S = 8.0
NAV_TIMEOUT_S = 30.0
ENGINE_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.05
PRODUCTION_GO_TO_S = 3.0
SORRY_PATH = "/sorry/"
MODE_POLL = "poll"
MODE_EVENTS = "events"

RECORDS: list[dict] = []
SETTINGS: dict = {"mode": MODE_POLL}


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    log_path = isolate_logs()
    install_instrumentation(args.mode)
    asyncio.run(run_queries(QUERIES))
    summary = summarize(RECORDS)
    json_path, md_path = write_outputs(RECORDS, summary)
    print(json_path)
    print(md_path)
    print(log_path)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Measure when Google's results DOM and load events arrive in the production browser setup")
    ap.add_argument("--mode", choices=[MODE_POLL, MODE_EVENTS], default=MODE_POLL, help="poll: query the results DOM every 50 ms; events: one DOM query at DOMContentLoaded, no polling during load")
    return ap.parse_args()


def isolate_logs() -> Path:
    log_path = Path(tempfile.mkdtemp(prefix="probe_google_")) / "query_log.jsonl"
    os.environ["WEBSEARCH_QUERY_LOG_PATH"] = str(log_path)
    return log_path


def install_instrumentation(mode: str) -> None:
    SETTINGS["mode"] = mode
    google._search_in_tab = measured_search_in_tab
    search_web.cache_write = lambda *args, **kwargs: None


async def run_queries(queries: list[str]) -> None:
    for query in queries:
        await search_web.search_web_workflow(query, language="en", engine_timeout=ENGINE_TIMEOUT_S)
        await asyncio.sleep(SPACING_S)


async def measured_search_in_tab(tab, query, max_results, partial, t0, search_url):
    record = {"query": query, "events": {}, "requests": 0, "error": None}
    await start_document_status_capture(tab)
    t_nav = time.perf_counter()
    await register_listeners(tab, record, t_nav)
    poller = asyncio.create_task(poll_results(tab, record, t_nav)) if SETTINGS["mode"] == MODE_POLL else None
    try:
        await tab.go_to(search_url, timeout=NAV_TIMEOUT_S)
        record["events"]["go_to_returned"] = elapsed_ms(t_nav)
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
    finally:
        if poller:
            poller.cancel()
    record["final_url"] = await tab.current_url
    record["results_at_end"] = await count_result_containers(tab)
    RECORDS.append(record)
    return [], None, None


async def register_listeners(tab, record: dict, t_nav: float) -> None:
    def mark(name):
        return lambda event: record["events"].setdefault(name, elapsed_ms(t_nav))

    def on_response(event):
        params = event.get("params") or {}
        if params.get("type") == ResourceType.DOCUMENT and params.get("frameId") == tab._target_id:
            record["events"].setdefault("document_response", elapsed_ms(t_nav))

    def on_request(event):
        record["requests"] += 1

    async def on_dom_content(event):
        record["events"].setdefault("dom_content_loaded", elapsed_ms(t_nav))
        if SETTINGS["mode"] == MODE_EVENTS:
            record["results_at_dom_content"] = await count_result_containers(tab)

    await tab.on(PageEvent.DOM_CONTENT_EVENT_FIRED, on_dom_content)
    await tab.on(PageEvent.LOAD_EVENT_FIRED, mark("load"))
    await tab.on(NetworkEvent.RESPONSE_RECEIVED, on_response)
    await tab.on(NetworkEvent.REQUEST_WILL_BE_SENT, on_request)


async def poll_results(tab, record: dict, t_nav: float) -> None:
    while "results_dom" not in record["events"]:
        count = await count_result_containers(tab)
        if count:
            record["events"]["results_dom"] = elapsed_ms(t_nav)
            record["results_at_first_sight"] = count
            return
        await asyncio.sleep(POLL_INTERVAL_S)


async def count_result_containers(tab) -> int:
    try:
        value = extract_value(await tab.execute_script(google._JS_WAIT))
    except Exception:
        return 0
    return int(value) if value else 0


def elapsed_ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def summarize(records: list[dict]) -> dict:
    valid = [r for r in records if r["error"] is None and SORRY_PATH not in r.get("final_url", "")]
    slow = [r for r in valid if r["events"].get("load", 0) > PRODUCTION_GO_TO_S * 1000]
    return {
        "runs": len(records),
        "valid_runs": len(valid),
        "excluded": [{"query": r["query"], "error": r["error"], "final_url": r.get("final_url")} for r in records if r not in valid],
        "percentiles_ms": {name: percentiles([r["events"][name] for r in valid if name in r["events"]]) for name in ("document_response", "dom_content_loaded", "results_dom", "load")},
        "mode": SETTINGS["mode"],
        "runs_without_results_dom": sum(1 for r in valid if "results_dom" not in r["events"]),
        "runs_with_results_at_dom_content": sum(1 for r in valid if r.get("results_at_dom_content")),
        "load_over_production_limit": len(slow),
        "slow_runs": [slow_row(r) for r in slow],
        "gap_load_minus_dom_ms": percentiles([r["events"]["load"] - r["events"]["dom_content_loaded"] for r in valid if "load" in r["events"] and "dom_content_loaded" in r["events"]]),
        "requests_before_end": percentiles([r["requests"] for r in valid]),
    }


def slow_row(record: dict) -> dict:
    return {"query": record["query"], "events": record["events"], "requests": record["requests"], "results_at_end": record["results_at_end"]}


def percentiles(values: list[int]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(ordered), "min": ordered[0], "p50": round(statistics.median(ordered)), "p90": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))], "max": ordered[-1]}


def write_outputs(records: list[dict], summary: dict) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    CANARY_JSON_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CANARY_JSON_DIR / f"probe_google_load_events_{SETTINGS['mode']}_{stamp}.json"
    md_path = REPORT_DIR / f"probe_google_load_events_{SETTINGS['mode']}_{stamp}.md"
    json_path.write_text(json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path.write_text(render_summary(summary, records), encoding="utf-8")
    return json_path, md_path


def render_summary(summary: dict, records: list[dict]) -> str:
    lines = [
        "# Google load-event probe",
        "",
        f"- Mode: {summary['mode']}",
        f"- Runs: {summary['runs']}, valid: {summary['valid_runs']}, excluded: {len(summary['excluded'])}",
        f"- Runs with load event later than {PRODUCTION_GO_TO_S} s (would fail in production): {summary['load_over_production_limit']}",
        f"- Valid runs where the results DOM never appeared (poll mode): {summary['runs_without_results_dom']}",
        f"- Valid runs with result containers present at DOMContentLoaded (events mode): {summary['runs_with_results_at_dom_content']}",
        "",
        "| event (ms after navigate) | n | min | p50 | p90 | max |",
        "|---|---|---|---|---|---|",
    ]
    for name, stats in summary["percentiles_ms"].items():
        lines.append(f"| {name} | " + " | ".join(str(stats[k]) for k in ("n", "min", "p50", "p90", "max")) + " |" if stats else f"| {name} | 0 | - | - | - | - |")
    gap = summary["gap_load_minus_dom_ms"]
    lines += ["", f"Load minus DOMContentLoaded (ms): {gap}", "", "## Runs with a load event later than the production limit", ""]
    lines += [f"- {row['query']}: {row['events']}, requests={row['requests']}, result containers at end={row['results_at_end']}" for row in summary["slow_runs"]] or ["(none)"]
    lines += ["", "## All runs", "", "| query | document_response | dom_content_loaded | results_dom | load | requests |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['query']} | " + " | ".join(str(r['events'].get(k, "-")) for k in ("document_response", "dom_content_loaded", "results_dom", "load")) + f" | {r['requests']} |" for r in records]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
