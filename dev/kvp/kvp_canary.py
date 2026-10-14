# INFRASTRUCTURE
import argparse
import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from dev.kvp.kvp_canary_logic import compare_runs, evaluate_case, render_canary_report
from dev.kvp.kvp_config import CANARY_CASES_PATH, CANARY_JSON_DIR, REPORT_DIR
from dev.kvp.kvp_load import read_jsonl, read_sidecar_body
from src.code_version import code_version
from src.scraper.chromium_scrape import scrape_url_chromium_workflow

SCRAPE_LOG_ENV = "WEBSEARCH_SCRAPE_LOG_PATH"
SCRAPE_LOG_NAME = "scrape_log.jsonl"
RUN_DIR_PREFIX = "kvp_canary_"

ScrapeOne = Callable[[dict], Awaitable[tuple[dict | None, str]]]


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    cases = load_cases(CANARY_CASES_PATH)
    run_dir = isolate_scrape_log()
    results = asyncio.run(run_cases(cases, make_scrape_one(run_dir)))
    baseline = load_baseline(args.baseline)
    comparison = compare_runs(baseline, results) if baseline is not None else None
    meta = build_meta(args.baseline)
    report = render_canary_report(meta, results, comparison)
    md_path, json_path = write_outputs(report, meta, results)
    print(md_path)
    print(json_path)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="KVP canary runner over a fixed URL list")
    ap.add_argument("--baseline", type=str, default=None, help="JSON written by an earlier canary run")
    return ap.parse_args()


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def isolate_scrape_log() -> Path:
    run_dir = Path(tempfile.mkdtemp(prefix=RUN_DIR_PREFIX))
    os.environ[SCRAPE_LOG_ENV] = str(run_dir / SCRAPE_LOG_NAME)
    return run_dir


def make_scrape_one(run_dir: Path) -> ScrapeOne:
    async def scrape_one(case: dict) -> tuple[dict | None, str]:
        before = len(read_jsonl(run_dir / SCRAPE_LOG_NAME))
        await scrape_url_chromium_workflow(case["url"])
        records = read_jsonl(run_dir / SCRAPE_LOG_NAME)
        if len(records) <= before:
            return None, ""
        record = records[-1]
        return record, read_sidecar_body(run_dir, record.get("content_path"))
    return scrape_one


async def run_cases(cases: list[dict], scrape_one: ScrapeOne) -> list[dict]:
    results = []
    for case in cases:
        record, body = await scrape_one(case)
        results.append(evaluate_case(case, record, body))
    return results


def load_baseline(path: str | None) -> list[dict] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))["results"]


def build_meta(baseline: str | None) -> dict:
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_version": code_version(),
        "cases_file": str(CANARY_CASES_PATH.name),
        "baseline": baseline,
    }


def write_outputs(report: str, meta: dict, results: list[dict]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CANARY_JSON_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    md_path = REPORT_DIR / f"kvp_canary_{stamp}.md"
    json_path = CANARY_JSON_DIR / f"kvp_canary_{stamp}.json"
    md_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return md_path, json_path


if __name__ == "__main__":
    main()
