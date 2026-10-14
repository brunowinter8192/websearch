# INFRASTRUCTURE
import json
import sys
from pathlib import Path

import pytest

import dev.kvp.kvp_report as kvp_report
from dev.kvp.kvp_config import SILENT_SCRAPE_LABELS
from dev.kvp.kvp_dives import group_dives
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


def test_report_lists_collapse_searches_with_pattern_and_host_facts(tmp_path, monkeypatch):
    cases = [json.loads(l) for l in (FIXTURE_DIR / "collapse_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    constructed_host = {
        "cpu_count": 14, "load_avg_start": [14.6, 9.1, 5.0], "cpu_busy_pct": 93.4,
        "top_cpu_processes": [{"name": "mds_stores", "cpu_s": 31.2, "procs": 1}], "errors": ["ps: 1 unparseable lines, first: 'x'"],
    }
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    lines = []
    for case in cases:
        record = dict(case["record"])
        if case["case"] == "2026-10-14T16:39:24Z":
            record["host"] = constructed_host
            record["code_version"] = "abc1234567"
        lines.append(json.dumps(record, ensure_ascii=False))
    (log_dir / "query_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = _run_report(tmp_path, monkeypatch, log_dir)

    collapse = report.split("## Collapse searches")[1].split("## Deep dive lane")[0]
    assert "Searches with fewer than 3 engines OK: 6" in collapse
    assert "slow_navigation=3" in collapse and "local_network=1" in collapse
    assert "load 14.6/14 cpus; busy 93.4 %; top: mds_stores 31.2s; errors: ps: 1 unparseable lines" in collapse
    assert collapse.count("| not recorded |") == 5
    assert "2026-10-14T16:39:36" not in collapse


def test_report_splits_the_focus_engine_by_code_version_and_names_page_load_timeouts(tmp_path, monkeypatch):
    cases = [json.loads(l) for l in (FIXTURE_DIR / "collapse_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    lines = []
    for case in cases:
        record = dict(case["record"])
        if case["case"] in ("2026-10-14T16:39:24Z", "2026-10-14T16:39:36Z"):
            record["code_version"] = "abc1234567"
        lines.append(json.dumps(record, ensure_ascii=False))
    (log_dir / "query_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = _run_report(tmp_path, monkeypatch, log_dir)

    table = report.split("## Engine google by code version")[1].split("## Collapse searches")[0]
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]] for line in table.splitlines() if line.startswith("| ") and not line.startswith("| code_version")}
    assert rows["all"][0] == "7"
    assert rows["all"][2].startswith("4/7")
    assert rows["abc1234567"][0] == "2"
    assert rows["abc1234567"][2].startswith("2/2")
    assert rows["unversioned"][2].startswith("2/5")


def test_report_shows_the_run_record_of_each_deep_dive_with_its_state(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    real = (FIXTURE_DIR / "deep_dive_log_real.jsonl").read_text(encoding="utf-8")
    constructed = (FIXTURE_DIR / "deep_dive_log_constructed.jsonl").read_text(encoding="utf-8")
    (log_dir / "deep_dive_log.jsonl").write_text(real + constructed, encoding="utf-8")

    report = _run_report(tmp_path, monkeypatch, log_dir)

    dives = report.split("### Run record per deep dive")[1].split("### Technical and relevance per pipe run")[0]
    rows = [line for line in dives.splitlines() if line.startswith("| 2026-")]
    assert len(rows) == 3
    complete = next(r for r in rows if "| complete |" in r)
    assert "205/229 (89.5 %)" in complete
    assert "book_footer=300, book_toc=75, images=730, site_footer=130, site_header=130" in complete
    assert "205 / 3222" in complete and "| websearch-pages |" in complete
    unclosed = next(r for r in rows if "docs.example.org" in r)
    assert "| no closing record |" in unclosed and "40 (seed=1, sitemap=39); failed feeders: navtree" in unclosed
    assert "| 30 | 28 |" in unclosed
    orphan = next(r for r in rows if "| no discovery record |" in r)
    assert "sre.google" in orphan and "| 4 | 4 |" in orphan
    assert "deep dive records: 6" in report


def test_group_dives_opens_a_new_dive_for_a_second_discovery_on_the_same_host():
    discovery = {"record_type": "discovery", "host": "a.test", "ok": True, "total": 2, "by_source": {}, "failed_feeders": {}}
    records = [
        {**discovery, "ts": "2026-10-15T09:00:00Z"},
        {"record_type": "scrape_round", "host": "a.test", "ts": "2026-10-15T09:01:00Z", "run_id": "r1", "urls_requested": 2, "files_written": 2},
        {**discovery, "ts": "2026-10-15T10:00:00Z"},
    ]

    dives = group_dives(records)

    assert [len(d["rounds"]) for d in dives] == [1, 0]
