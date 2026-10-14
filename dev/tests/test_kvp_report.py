# INFRASTRUCTURE
import json
import sys
from pathlib import Path

import pytest

import dev.kvp.kvp_report as kvp_report
from dev.kvp.kvp_config import SILENT_SCRAPE_LABELS
from dev.kvp.kvp_indicators import relevance_indicators

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kvp"
SIDECAR_HEADER = "<!-- url: {url} -->\n<!-- ts: {ts} -->\n<!-- bytes: 0 -->\n<!-- mode: filtered -->\n<!-- engine: chromium -->\n\n"


# FUNCTIONS

def test_report_lists_every_silent_scrape_and_the_counter_check(tmp_path, monkeypatch):
    cases = [json.loads(l) for l in (FIXTURE_DIR / "scrape_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    log_dir = _write_scrape_log(tmp_path, cases)
    report = _run_report(tmp_path, monkeypatch, log_dir)

    expected_silent = [c for c in cases if c["expected"] in SILENT_SCRAPE_LABELS]
    assert f"### Ad hoc scrapes ({len(expected_silent)})" in report
    assert all(c["record"]["url"] in report for c in expected_silent)
    assert "### Counter-check: marked failed or error status, classified usable (5)" in report


def test_report_window_excludes_records_outside_since_until(tmp_path, monkeypatch):
    cases = [json.loads(l) for l in (FIXTURE_DIR / "scrape_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    log_dir = _write_scrape_log(tmp_path, cases)
    report = _run_report(tmp_path, monkeypatch, log_dir, "--since", "2026-09-17", "--until", "2026-09-18")

    in_window = [c for c in cases if "2026-09-17" <= c["record"]["ts"][:10] < "2026-09-18"]
    assert f"scrapes: {len(in_window)}" in report


def test_relevance_attributes_scrape_within_three_hours_and_reports_rank():
    searches = [{"record": {"search_key": "k1", "code_version": "abc"}, "verdicts": {}}]
    drilldowns = [{"ts": "2026-10-01T10:00:00.000Z", "search_key": "k1", "urls": ["https://a.example/1", "https://b.example/2/"]}]
    scrapes = [
        {"ts": "2026-10-01T11:00:00.000Z", "url": "https://b.example/2"},
        {"ts": "2026-10-01T14:30:00.000Z", "url": "https://a.example/1"},
    ]

    result = relevance_indicators(searches, drilldowns, scrapes)

    assert result["searches_with_scrape"] == 1
    assert result["rank_counts"] == {2: 1}


def _write_scrape_log(tmp_path: Path, cases: list[dict]) -> Path:
    log_dir = tmp_path / "logs"
    (log_dir / "scrape_content").mkdir(parents=True)
    lines = []
    for case in cases:
        record = dict(case["record"])
        if record.get("content_path"):
            sidecar = log_dir / record["content_path"]
            sidecar.write_text(SIDECAR_HEADER.format(url=record["url"], ts=record["ts"]) + case["body"], encoding="utf-8")
        lines.append(json.dumps(record, ensure_ascii=False))
    (log_dir / "scrape_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_dir


def _run_report(tmp_path: Path, monkeypatch, log_dir: Path, *extra: str) -> str:
    report_dir = tmp_path / "md"
    monkeypatch.setattr(kvp_report, "REPORT_DIR", report_dir)
    monkeypatch.setattr(sys, "argv", [
        "kvp_report", "--log-dir", str(log_dir),
        "--rag-search-log", str(tmp_path / "missing_rag.jsonl"),
        "--collection-dir", str(tmp_path / "missing_collection"),
        *extra,
    ])
    kvp_report.main()
    [path] = list(report_dir.glob("kvp_report_*.md"))
    return path.read_text(encoding="utf-8")
