# INFRASTRUCTURE
from pathlib import Path


# FUNCTIONS

def count_outcomes(records: list[dict]) -> dict:
    counts = {"OK": 0, "EMPTY_PARSED": 0, "NO_CONTAINERS": 0, "BLOCKED": 0, "ERROR": 0}
    for r in records:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return counts


def _build_header(run_ts: str, records: list[dict], by_num: dict, num_variants: list, nav_delay_s: float) -> list[str]:
    return [
        f"# Google DOM Path Probe (Path A) — {run_ts}",
        "",
        "Reproduces src/search/engines/google.py's exact current selectors (div.MjjYud / h3 / "
        ".LC20lb / closest a[href^=\"http\"]) against real live Google navigations, self-contained "
        "(no src/ import), pydoll stealth stack matching src/search/browser.py's shape exactly — "
        "no extra stealth beyond what production has, so this measures production's own failure, "
        "not a more-stealthed setup's success.",
        "",
        f"**Queries:** {len(by_num[num_variants[0]])} (see `dev/access_recovery/queries.json`, "
        "shared with the Path B probe) — the same 10-query, axis-tagged set "
        "`dev/search_pipeline/26_brave_probe.py` uses.",
        f"**Navigations:** {len(records)} total ({len(num_variants)} num-variants x "
        f"{len(by_num[num_variants[0]])} queries).",
        f"**Pacing:** {nav_delay_s}s between every individual navigation (not just every query) — "
        "matched to production's own google rate limiter "
        "(`RateLimiter(max_requests=4, window_seconds=60)` in `src/search/engines/google.py`, "
        "~15s/request in steady state), so this probe's own traffic pattern cannot induce a "
        "rate-limit event production's real pacing would not also risk. See "
        "`process-docs/engine_expansion/brave_reeval_2026-07-21.md` for why this matters — a "
        "prior probe with no inter-query delay measured a block, not the thing it was built to "
        "measure.",
        "",
    ]


def _build_outcome_counts_section(counts: dict) -> list[str]:
    return [
        "## Outcome counts (all navigations)",
        "",
        f"- **OK** (real results extracted): {counts['OK']}",
        f"- **EMPTY_PARSED** (containers found, title/url extraction found zero — the production "
        f"failure shape this milestone exists to explain): {counts['EMPTY_PARSED']}",
        f"- **NO_CONTAINERS** (div.MjjYud never appeared): {counts['NO_CONTAINERS']}",
        f"- **BLOCKED** (landed on /sorry/): {counts['BLOCKED']}",
        f"- **ERROR**: {counts['ERROR']}",
        "",
    ]


def _build_num_variant_section(by_num: dict, num_variants: list) -> list[str]:
    lines = ["## num=100 vs num=10", ""]
    for num in num_variants:
        recs = by_num[num]
        c = count_outcomes(recs)
        lines.append(f"**num={num}** ({len(recs)} navigations): OK={c['OK']}, "
                      f"EMPTY_PARSED={c['EMPTY_PARSED']}, NO_CONTAINERS={c['NO_CONTAINERS']}, "
                      f"BLOCKED={c['BLOCKED']}, ERROR={c['ERROR']}")
    lines.append("")
    return lines


def _build_per_navigation_table(records: list[dict]) -> list[str]:
    lines = [
        "## Per-navigation results",
        "",
        "| # | num | Axis | Query | Outcome | Containers | Count | Elapsed ms |",
        "|---|-----|------|-------|---------|------------|-------|------------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:40].replace("|", "\\|")
        lines.append(
            f"| {i} | {r['num']} | {r['axis']} | {q} | {r['outcome']} | "
            f"{r.get('containers_count')} | {r['count']} | {r['elapsed_ms']} |"
        )
    lines.append("")
    return lines


def _build_ok_samples_section(records: list[dict]) -> list[str]:
    ok_recs = [r for r in records if r["outcome"] == "OK"]
    if not ok_recs:
        return []
    lines = ["## OK samples (quality eyeball)", ""]
    for r in ok_recs:
        lines.append(f"### num={r['num']} — {r['query']} ({r['axis']}) — {r['count']} results")
        lines.append("")
        for s in r["samples"]:
            lines.append(f"- **{s['title']}** — {s['url']}")
        lines.append("")
    return lines


def _build_empty_parsed_section(records: list[dict], run_ts: str) -> list[str]:
    empty_recs = [r for r in records if r["outcome"] == "EMPTY_PARSED"]
    if not empty_recs:
        return []
    lines = [
        "## EMPTY_PARSED diagnostic evidence",
        "",
        "For each: container_count / page-wide h3 count / page-wide http-anchor count, then "
        "per-sampled-container has_h3 / has_lc20lb / http_anchor_count / child_tags. Full "
        f"outerHTML samples and raw page HTML saved under `dev/access_recovery/html/"
        f"google_dom_probe_{run_ts}/` (gitignored — local evidence, not carried in the repo).",
        "",
    ]
    for r in empty_recs:
        d = r.get("diagnostic") or {}
        lines.append(f"### num={r['num']} — {r['query']} ({r['axis']})")
        lines.append("")
        lines.append(
            f"- container_count={d.get('container_count')}, "
            f"page_wide_h3_count={d.get('page_wide_h3_count')}, "
            f"page_wide_http_anchor_count={d.get('page_wide_http_anchor_count')}"
        )
        for s in d.get("samples", []):
            lines.append(
                f"- sample[{s['index']}]: has_h3={s['has_h3']}, has_lc20lb={s['has_lc20lb']}, "
                f"http_anchor_count={s['http_anchor_count']}, "
                f"total_anchor_count={s['total_anchor_count']}"
            )
            lines.append(f"  - child_tags: `{s['child_tags']}`")
        lines.append("")
    return lines


def _build_blocked_section(records: list[dict]) -> list[str]:
    blocked_recs = [r for r in records if r["outcome"] == "BLOCKED"]
    if not blocked_recs:
        return []
    lines = ["## BLOCKED details", ""]
    for r in blocked_recs:
        lines.append(f"- num={r['num']} — {r['query']} ({r['axis']}) — landed_url: "
                     f"`{r.get('landed_url')}`")
    lines.append("")
    return lines


def _build_error_section(records: list[dict]) -> list[str]:
    error_recs = [r for r in records if r["outcome"] == "ERROR"]
    if not error_recs:
        return []
    lines = ["## ERROR details", ""]
    for r in error_recs:
        lines.append(f"- num={r['num']} — {r['query']} ({r['axis']}) — `{r.get('error')}`")
    lines.append("")
    return lines


def write_report(records: list[dict], run_ts: str, report_dir: Path,
                  num_variants: list, nav_delay_s: float) -> Path:
    path = report_dir / f"google_dom_probe_{run_ts}.md"
    by_num = {n: [r for r in records if r["num"] == n] for n in num_variants}
    counts = count_outcomes(records)

    lines = []
    lines += _build_header(run_ts, records, by_num, num_variants, nav_delay_s)
    lines += _build_outcome_counts_section(counts)
    lines += _build_num_variant_section(by_num, num_variants)
    lines += _build_per_navigation_table(records)
    lines += _build_ok_samples_section(records)
    lines += _build_empty_parsed_section(records, run_ts)
    lines += _build_blocked_section(records)
    lines += _build_error_section(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
