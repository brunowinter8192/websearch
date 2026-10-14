# INFRASTRUCTURE
from dev.kvp.kvp_classify import classify_scrape
from dev.kvp.kvp_config import CANARY_SCRAPE_ERROR

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
CHANGE_FIXED = "fixed"
CHANGE_REGRESSED = "regressed"
CHANGE_VERDICT_CHANGED = "verdict changed"
CHANGE_UNCHANGED = "unchanged"
CHANGE_NEW = "new case"


# FUNCTIONS

def evaluate_case(case: dict, record: dict | None, body: str) -> dict:
    if record is None:
        return _scrape_error_result(case)
    verdict = classify_scrape(record, body)
    missing = [needle for needle in case.get("must_contain", []) if needle not in body]
    verdict_ok = verdict.label == case["expected"]
    content_ok = None if "must_contain" not in case else not missing
    return {
        "name": case["name"],
        "url": case["url"],
        "volatile": bool(case.get("volatile")),
        "expected": case["expected"],
        "verdict": verdict.label,
        "evidence": verdict.evidence,
        "verdict_ok": verdict_ok,
        "content_ok": content_ok,
        "missing": missing,
        "status": STATUS_PASS if verdict_ok and content_ok is not False else STATUS_FAIL,
        "http_status": record.get("http_status"),
        "bytes_returned": record.get("bytes_returned"),
        "bytes_raw_markdown": record.get("bytes_raw_markdown"),
        "content_source": record.get("content_source"),
        "code_version": record.get("code_version"),
    }


def compare_runs(baseline: list[dict], current: list[dict]) -> list[dict]:
    baseline_by_name = {r["name"]: r for r in baseline}
    return [_compare_case(baseline_by_name.get(r["name"]), r) for r in current]


def summarize(results: list[dict]) -> dict:
    stable = [r for r in results if not r["volatile"]]
    volatile = [r for r in results if r["volatile"]]
    return {
        "cases": len(results),
        "stable_pass": sum(1 for r in stable if r["status"] == STATUS_PASS),
        "stable_total": len(stable),
        "volatile_pass": sum(1 for r in volatile if r["status"] == STATUS_PASS),
        "volatile_total": len(volatile),
    }


def render_canary_report(meta: dict, results: list[dict], comparison: list[dict] | None) -> str:
    sections = [
        _render_header(meta, summarize(results)),
        _render_results(results),
        _render_comparison(comparison, meta["baseline"]) if comparison is not None else "",
    ]
    return "\n\n".join(s for s in sections if s) + "\n"


def _scrape_error_result(case: dict) -> dict:
    return {
        "name": case["name"], "url": case["url"], "volatile": bool(case.get("volatile")),
        "expected": case["expected"], "verdict": CANARY_SCRAPE_ERROR, "evidence": "no scrape record written",
        "verdict_ok": False, "content_ok": None if "must_contain" not in case else False,
        "missing": list(case.get("must_contain", [])), "status": STATUS_FAIL, "http_status": None,
        "bytes_returned": None, "bytes_raw_markdown": None, "content_source": None, "code_version": None,
    }


def _compare_case(before: dict | None, after: dict) -> dict:
    return {
        "name": after["name"],
        "volatile": after["volatile"],
        "change": _change_kind(before, after),
        "before_verdict": before["verdict"] if before else None,
        "after_verdict": after["verdict"],
        "before_status": before["status"] if before else None,
        "after_status": after["status"],
        "before_content_ok": before["content_ok"] if before else None,
        "after_content_ok": after["content_ok"],
        "before_bytes": before["bytes_returned"] if before else None,
        "after_bytes": after["bytes_returned"],
        "after_content_source": after["content_source"],
    }


def _change_kind(before: dict | None, after: dict) -> str:
    if before is None:
        return CHANGE_NEW
    if before["status"] == STATUS_FAIL and after["status"] == STATUS_PASS:
        return CHANGE_FIXED
    if before["status"] == STATUS_PASS and after["status"] == STATUS_FAIL:
        return CHANGE_REGRESSED
    if before["verdict"] != after["verdict"]:
        return CHANGE_VERDICT_CHANGED
    return CHANGE_UNCHANGED


def _render_header(meta: dict, summary: dict) -> str:
    lines = [
        "# KVP canary run",
        "",
        f"- Generated: {meta['generated']}",
        f"- Code version: {meta['code_version']}",
        f"- Cases file: `{meta['cases_file']}`",
        f"- Baseline: {meta['baseline'] or 'none'}",
        f"- Stable cases passing: {summary['stable_pass']}/{summary['stable_total']}",
        f"- Volatile cases passing: {summary['volatile_pass']}/{summary['volatile_total']} (they can flip between runs, see the comparison)",
    ]
    return "\n".join(lines)


def _render_results(results: list[dict]) -> str:
    rows = [
        [r["name"] + (" (volatile)" if r["volatile"] else ""), r["expected"], r["verdict"], _tick(r["verdict_ok"]), _content_cell(r),
         r["http_status"], r["bytes_returned"], r["bytes_raw_markdown"], r["content_source"] or "-", r["status"]]
        for r in results
    ]
    headers = ["case", "expected", "verdict", "verdict ok", "content check", "http", "bytes returned", "bytes raw", "content_source", "status"]
    return "## Results\n\n" + _table(headers, rows)


def _render_comparison(comparison: list[dict], baseline_path: str | None) -> str:
    stable = [c for c in comparison if not c["volatile"]]
    volatile = [c for c in comparison if c["volatile"]]
    return "\n\n".join([
        f"## Comparison with baseline `{baseline_path}`",
        "### Stable cases\n\n" + _comparison_table(stable),
        "### Volatile cases (a flip here is not read as a regression)\n\n" + _comparison_table(volatile),
    ])


def _comparison_table(rows: list[dict]) -> str:
    cells = [
        [c["name"], c["change"], f"{c['before_verdict']} -> {c['after_verdict']}", f"{c['before_status']} -> {c['after_status']}",
         f"{c['before_content_ok']} -> {c['after_content_ok']}", f"{c['before_bytes']} -> {c['after_bytes']}", c["after_content_source"] or "-"]
        for c in rows
    ]
    return _table(["case", "change", "verdict", "status", "content check", "bytes returned", "content_source after"], cells)


def _content_cell(result: dict) -> str:
    if result["content_ok"] is None:
        return "-"
    return "PASS" if result["content_ok"] else "FAIL: missing " + ", ".join(result["missing"])


def _tick(value: bool) -> str:
    return "yes" if value else "no"


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "(none)"
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |" for row in rows]
    return "\n".join(lines)
