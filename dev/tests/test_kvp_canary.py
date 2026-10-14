# INFRASTRUCTURE
import asyncio
import json
from pathlib import Path

from dev.kvp.kvp_canary import load_cases, run_cases
from dev.kvp.kvp_canary_logic import (
    CHANGE_FIXED,
    CHANGE_NEW,
    CHANGE_REGRESSED,
    CHANGE_UNCHANGED,
    STATUS_FAIL,
    STATUS_PASS,
    compare_runs,
    evaluate_case,
    render_canary_report,
    summarize,
)
from dev.kvp.kvp_config import (
    CANARY_CASES_PATH,
    CANARY_SCRAPE_ERROR,
    SCRAPE_BLOCKED,
    SCRAPE_CHALLENGE,
    SCRAPE_FILTERED_TO_NOTHING,
    SCRAPE_HTTP_ERROR_PAGE,
    SCRAPE_LOGIN_WALL,
    SCRAPE_USABLE,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kvp"
KNOWN_LABELS = {SCRAPE_USABLE, SCRAPE_BLOCKED, SCRAPE_CHALLENGE, SCRAPE_LOGIN_WALL, SCRAPE_HTTP_ERROR_PAGE, SCRAPE_FILTERED_TO_NOTHING}


# FUNCTIONS

def _fixture_case(name: str) -> dict:
    for line in (FIXTURE_DIR / "scrape_cases.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["case"] == name:
            return entry
    raise KeyError(name)


def test_case_list_uses_known_labels_unique_names_and_the_three_empty_filter_urls():
    cases = load_cases(CANARY_CASES_PATH)
    urls = {c["url"] for c in cases}

    assert len({c["name"] for c in cases}) == len(cases)
    assert {c["expected"] for c in cases} <= KNOWN_LABELS
    assert "https://vorschriften.bgn-branchenwissen.de/daten/gv/eg_2004_853/a35.htm" in urls
    assert "https://dbis.ur.de/UBFM/resources?q=JSTOR" in urls
    assert "https://dbis.ur.de/UBFM/resources?q=Business+Source" in urls
    assert all(c.get("must_contain") for c in cases if c["name"].startswith("empty_filter_dbis"))


def test_empty_filter_record_fails_when_usable_is_expected():
    fixture = _fixture_case("bgn_branchenwissen_filtered_to_1B")
    case = {"name": "bgn", "url": fixture["record"]["url"], "expected": SCRAPE_USABLE, "must_contain": ["Sterilisationsvorrichtungen"]}

    result = evaluate_case(case, fixture["record"], fixture["body"])

    assert result["verdict"] == SCRAPE_FILTERED_TO_NOTHING
    assert result["verdict_ok"] is False
    assert result["content_ok"] is False
    assert result["status"] == STATUS_FAIL


def test_pinned_block_passes_when_verdict_matches_the_pinned_label():
    fixture = _fixture_case("cosdna_403_cloudflare_506B")
    case = {"name": "cosdna", "url": fixture["record"]["url"], "expected": SCRAPE_BLOCKED}

    result = evaluate_case(case, fixture["record"], fixture["body"])

    assert result["status"] == STATUS_PASS
    assert result["content_ok"] is None


def test_inverse_case_passes_with_content_marker_in_body():
    fixture = _fixture_case("eclecticlight_crawl4ai_false_real_content")
    case = {"name": "eclectic", "url": fixture["record"]["url"], "expected": SCRAPE_USABLE, "must_contain": ["Spotlight"]}

    result = evaluate_case(case, fixture["record"], fixture["body"])

    assert result["status"] == STATUS_PASS


def test_usable_verdict_with_missing_marker_still_fails_on_content():
    fixture = _fixture_case("eclecticlight_crawl4ai_false_real_content")
    case = {"name": "eclectic", "url": fixture["record"]["url"], "expected": SCRAPE_USABLE, "must_contain": ["JSTOR"]}

    result = evaluate_case(case, fixture["record"], fixture["body"])

    assert result["verdict_ok"] is True
    assert result["content_ok"] is False
    assert result["status"] == STATUS_FAIL
    assert result["missing"] == ["JSTOR"]


def test_missing_record_is_reported_as_scrape_error():
    case = {"name": "x", "url": "https://example.com/", "expected": SCRAPE_USABLE}

    result = evaluate_case(case, None, "")

    assert result["verdict"] == CANARY_SCRAPE_ERROR
    assert result["status"] == STATUS_FAIL


def test_run_cases_scrapes_every_case_in_order_and_evaluates_it():
    fixtures = {f["record"]["url"]: f for f in (_fixture_case(n) for n in ("cosdna_403_cloudflare_506B", "mojeek_verification_required_185B"))}
    cases = [
        {"name": "cosdna", "url": "https://www.cosdna.com/eng/cosmetic_8dde453460.html", "expected": SCRAPE_BLOCKED},
        {"name": "mojeek", "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial", "expected": SCRAPE_CHALLENGE, "volatile": True},
    ]
    seen = []

    async def fake_scrape_one(case):
        seen.append(case["name"])
        entry = fixtures[case["url"]]
        return entry["record"], entry["body"]

    results = asyncio.run(run_cases(cases, fake_scrape_one))

    assert seen == ["cosdna", "mojeek"]
    assert [r["status"] for r in results] == [STATUS_PASS, STATUS_PASS]
    assert [r["volatile"] for r in results] == [False, True]


def test_compare_marks_fix_regression_unchanged_and_new_case():
    baseline = [_result("a", STATUS_FAIL, SCRAPE_FILTERED_TO_NOTHING, 1), _result("b", STATUS_PASS, SCRAPE_USABLE, 900), _result("c", STATUS_PASS, SCRAPE_BLOCKED, 120)]
    current = [_result("a", STATUS_PASS, SCRAPE_USABLE, 16742), _result("b", STATUS_FAIL, SCRAPE_BLOCKED, 120), _result("c", STATUS_PASS, SCRAPE_BLOCKED, 120), _result("d", STATUS_PASS, SCRAPE_USABLE, 50)]

    changes = {c["name"]: c["change"] for c in compare_runs(baseline, current)}

    assert changes == {"a": CHANGE_FIXED, "b": CHANGE_REGRESSED, "c": CHANGE_UNCHANGED, "d": CHANGE_NEW}


def test_report_lists_volatile_cases_separately_in_the_comparison():
    baseline = [_result("stable", STATUS_PASS, SCRAPE_USABLE, 10), _result("flaky", STATUS_PASS, SCRAPE_CHALLENGE, 185, volatile=True)]
    current = [_result("stable", STATUS_PASS, SCRAPE_USABLE, 10), _result("flaky", STATUS_FAIL, SCRAPE_USABLE, 7665, volatile=True)]
    meta = {"generated": "2026-10-15T00:00:00Z", "code_version": "abc", "cases_file": "canary_cases.json", "baseline": "base.json"}

    report = render_canary_report(meta, current, compare_runs(baseline, current))

    stable_section, volatile_section = report.split("### Volatile cases")
    assert "| stable |" in stable_section
    assert "| flaky |" not in stable_section
    assert "| flaky |" in volatile_section
    assert summarize(current) == {"cases": 2, "stable_pass": 1, "stable_total": 1, "volatile_pass": 0, "volatile_total": 1}


def _result(name, status, verdict, returned, volatile=False):
    return {
        "name": name, "url": f"https://{name}.example/", "volatile": volatile, "expected": SCRAPE_USABLE, "verdict": verdict,
        "evidence": "", "verdict_ok": status == STATUS_PASS, "content_ok": None, "missing": [], "status": status,
        "http_status": 200, "bytes_returned": returned, "bytes_raw_markdown": 100, "content_source": None, "code_version": "abc",
    }
