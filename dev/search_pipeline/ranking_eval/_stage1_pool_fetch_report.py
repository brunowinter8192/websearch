# INFRASTRUCTURE
from pathlib import Path

from _stage1_pool_fetch_config import MODES

_STATUS_HINTS: dict[str, str] = {
    "TIMEOUT_WATCHDOG":      "watchdog timeout",
    "TIMEOUT_NONCOOP":       "non-cooperative",
    "TIMEOUT_HTTPX":         "httpx timeout",
    "ERROR_BROWSER":         "Chrome error",
    "ERROR_HTTP":            "HTTP error",
    "ERROR_PARSE":           "parse error",
    "ERROR_OTHER":           "unexpected error",
    "RATE_SKIP":             "rate skip",
    "EMPTY":                 "empty",
    "ERROR":                 "error",
}


# FUNCTIONS

def _save_engine_report(
    ts_dir: Path, mode: str, slug: str, query: str, fetched_ts: str,
    engine_stats: dict, oracle_pool: list[dict],
    raw_count: int, capped_count: int,
) -> None:
    oracle_count = len(oracle_pool)

    rows = _engine_breakdown_rows(engine_stats)

    lines = [
        f"# Engine Report — {mode} × {query}",
        "",
        f"**Mode:** {mode}",
        f"**Query:** {query}",
        f"**Fetched:** {fetched_ts}",
        "",
        "## Pool Sizes",
        "",
        "| Stage | Count |",
        "|-------|------:|",
        f"| Raw results | {raw_count} |",
        f"| Capped (K=google_count) | {capped_count} |",
        f"| Oracle pool (capped — no URL filter) | {oracle_count} |",
        "",
        "## Engine Breakdown",
        "",
        "| Engine | URLs | Status | Reason | ms |",
        "|--------|-----:|--------|--------|----|",
    ]
    for n, eng, status, reason, ms in rows:
        lines.append(f"| {eng} | {n} | {status} | {reason} | {ms} |")

    lines += [
        "",
        f"## Pool URL Listing (oracle pool — {oracle_count} URLs, sorted by URL)",
        "",
    ]
    lines += _pool_url_listing(oracle_pool)

    (ts_dir / f"{mode}_{slug}_engine_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _engine_breakdown_rows(engine_stats: dict) -> list[tuple]:
    rows: list[tuple] = []
    for eng, info in engine_stats.items():
        status = info.get("status", "")
        ms     = info.get("search_ms", 0)
        n      = info.get("result_count", 0)
        drop   = info.get("drop_reason") or ""
        reason = drop if drop else (_STATUS_HINTS.get(status, "") if status != "OK" else "")
        rows.append((n, eng, status, reason, ms))
    rows.sort(key=lambda x: (-x[0], x[1]))
    return rows


def _pool_url_listing(oracle_pool: list[dict]) -> list[str]:
    lines = []
    for i, m in enumerate(oracle_pool, 1):
        title   = (m.get("title")   or "").strip().replace("\n", " ")[:100]
        snippet = (m.get("snippet") or "").strip().replace("\n", " ")[:200]
        lines += [
            f"{i}. {m['url']}",
            f"   Title: {title}",
            f"   Snippet: {snippet}",
            "",
        ]
    return lines


def _save_engine_summary(ts_dir: Path, rows: list[dict], ts: str) -> None:
    engine_data = _aggregate_engine_data(rows)

    lines = _render_engine_aggregate(engine_data, rows, ts)
    lines += _render_mode_availability(engine_data)

    lines.append("")
    (ts_dir / "engine_report_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _aggregate_engine_data(rows: list[dict]) -> dict[str, dict]:
    engine_data: dict[str, dict] = {}
    for row in rows:
        mode = row["mode"]
        for eng, info in row["engine_stats"].items():
            if eng not in engine_data:
                engine_data[eng] = {
                    "n":             0,
                    "ok":            0,
                    "total_urls":    0,
                    "status_counts": {},
                    "mode_ok":       {m: 0 for m in MODES},
                    "mode_n":        {m: 0 for m in MODES},
                }
            d      = engine_data[eng]
            status = info.get("status", "ERROR_OTHER")
            n_urls = info.get("result_count", 0)
            d["n"]          += 1
            d["total_urls"] += n_urls
            d["status_counts"][status] = d["status_counts"].get(status, 0) + 1
            d["mode_n"][mode] += 1
            if status == "OK":
                d["ok"] += 1
                d["mode_ok"][mode] += 1
    return engine_data


def _render_engine_aggregate(engine_data: dict[str, dict], rows: list[dict], ts: str) -> list[str]:
    _EMPTY_STATUSES   = {"EMPTY"}
    _TIMEOUT_STATUSES = {"TIMEOUT_WATCHDOG", "TIMEOUT_NONCOOP", "TIMEOUT_HTTPX"}
    _ERROR_STATUSES   = {"ERROR_BROWSER", "ERROR_HTTP", "ERROR_PARSE", "ERROR_OTHER", "ERROR"}

    lines = [
        "# Engine Report Summary — value_eval_v2",
        "",
        f"**Run:** {ts}",
        f"**Pairs:** {len(rows)} (4 modes × 4 queries)",
        "",
        "## Per-Engine Aggregate",
        "",
        "| Engine | n | OK | EMPTY% | TIMEOUT% | ERROR% | Total URLs | Mean URLs/Pool | Dominant Failure |",
        "|--------|---|----|----|----|---|---|---|---|",
    ]
    for eng in sorted(engine_data):
        d   = engine_data[eng]
        n   = d["n"]
        sc  = d["status_counts"]
        tu  = d["total_urls"]
        mu  = f"{tu / n:.1f}" if n else "0"
        emp = sum(sc.get(s, 0) for s in _EMPTY_STATUSES)
        tmo = sum(sc.get(s, 0) for s in _TIMEOUT_STATUSES)
        err = sum(sc.get(s, 0) for s in _ERROR_STATUSES)
        dom = _dominant_failure(sc)
        lines.append(
            f"| {eng} | {n} | {d['ok']} | {_pct(emp, n)}"
            f" | {_pct(tmo, n)} | {_pct(err, n)} | {tu} | {mu} | {dom} |"
        )
    return lines


def _pct(count: int, total: int) -> str:
    return str(round(count / total * 100)) if total else "0"


def _dominant_failure(sc: dict) -> str:
    non_ok = {k: v for k, v in sc.items() if k != "OK"}
    return max(non_ok, key=non_ok.get) if non_ok else "—"


def _render_mode_availability(engine_data: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Per-Mode Engine Availability (OK out of 4 pairs per mode)",
        "",
        "| Engine | general | pdf | books | docs |",
        "|--------|---------|-----|-------|------|",
    ]
    for eng in sorted(engine_data):
        d     = engine_data[eng]
        cells = " | ".join(f"{d['mode_ok'][m]}/{d['mode_n'][m]}" for m in MODES)
        lines.append(f"| {eng} | {cells} |")
    return lines
