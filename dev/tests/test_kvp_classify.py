# INFRASTRUCTURE
import json
from pathlib import Path

import pytest

from dev.kvp.kvp_classify import (
    classify_collapse,
    classify_collection_file,
    classify_engine_run,
    classify_pipe_record,
    classify_scrape,
    find_duplicate_files,
)
from dev.kvp.kvp_config import COLLECTION_DUPLICATE, SCRAPE_USABLE, SILENT_SCRAPE_LABELS

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kvp"


# FUNCTIONS

def _load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines() if line.strip()]


SCRAPE_CASES = _load_jsonl("scrape_cases.jsonl")
ENGINE_CASES = _load_jsonl("engine_cases.jsonl")
COLLECTION_FIXTURE = json.loads((FIXTURE_DIR / "collection_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", SCRAPE_CASES, ids=[c["case"] for c in SCRAPE_CASES])
def test_scrape_verdict_matches_observed_case(case):
    verdict = classify_scrape(case["record"], case["body"])

    assert verdict.label == case["expected"]


def test_silent_scrape_cases_cover_every_observed_class():
    observed = {c["expected"] for c in SCRAPE_CASES}

    assert set(SILENT_SCRAPE_LABELS) <= observed


def test_inverse_cases_are_flagged_failed_by_crawl4ai_but_classified_usable():
    inverse = [c for c in SCRAPE_CASES if c["record"].get("crawl4ai_success") is False and c["expected"] == SCRAPE_USABLE]

    assert len(inverse) == 5
    assert all(classify_scrape(c["record"], c["body"]).label == SCRAPE_USABLE for c in inverse)


@pytest.mark.parametrize("case", ENGINE_CASES, ids=[c["case"] for c in ENGINE_CASES])
def test_engine_verdict_matches_observed_case(case):
    verdict = classify_engine_run(case["stats"])

    assert verdict.label == case["expected"]


@pytest.mark.parametrize("case", COLLECTION_FIXTURE["cases"], ids=[c["case"] for c in COLLECTION_FIXTURE["cases"]])
def test_collection_file_verdict(case):
    verdict = classify_collection_file(case["body"])

    assert (verdict.label if verdict else None) == case["expected"]


def test_duplicate_pair_flags_only_the_later_file():
    files = [{"name": f["name"], "body": f["body"]} for f in COLLECTION_FIXTURE["duplicate_pair"]]

    duplicates = find_duplicate_files(files)

    assert list(duplicates) == ["sre_google_books_building_secure_reliable_systems.md"]
    assert duplicates["sre_google_books_building_secure_reliable_systems.md"].label == COLLECTION_DUPLICATE


def test_successful_pipe_record_is_usable():
    record = json.loads((FIXTURE_DIR / "pipe_record.json").read_text(encoding="utf-8"))

    assert classify_pipe_record(record).label == SCRAPE_USABLE


COLLAPSE_CASES = _load_jsonl("collapse_cases.jsonl")
COLLAPSED = [c for c in COLLAPSE_CASES if c["expected"]]


@pytest.mark.parametrize("case", COLLAPSED, ids=[c["case"] for c in COLLAPSED])
def test_collapse_pattern_matches_observed_search(case):
    verdict = classify_collapse(case["record"]["engines"])

    assert verdict.label == case["expected"]


def test_collapse_evidence_names_the_observed_signals():
    by_case = {c["case"]: classify_collapse(c["record"]["engines"]) for c in COLLAPSED}

    assert by_case["2026-09-24T17:13:08Z"].evidence == "7 engines ERR_CONNECTION_REFUSED, HTTP errors from openalex"
    assert by_case["2026-10-10T12:09:15Z"].evidence == "5 watchdog timeouts, 5 without diagnosis"
    assert by_case["2026-09-15T11:52:18Z"].evidence == "blocked: brave, yandex"
