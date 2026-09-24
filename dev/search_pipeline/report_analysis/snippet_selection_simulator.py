#!/usr/bin/env python3
"""Snippet selection simulator — dry-run of new selection logic against existing smoke baseline."""

# INFRASTRUCTURE
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from _lib.parse import parse_smoke_report
from _lib.text  import strip_bloat, lexical_density

REPORT_DIR = SCRIPT_DIR / "md"
_smoke_candidates = sorted(REPORT_DIR.glob("pipeline_smoke_*.md"), reverse=True)
if not _smoke_candidates:
    raise FileNotFoundError(f"No pipeline_smoke_*.md found in {REPORT_DIR}")
SMOKE_REPORT = _smoke_candidates[0]

MIN_FLOOR = 40  # minimum clean_len for a non-floor snippet


# ORCHESTRATOR

# Run simulation over smoke report and write results
def run_simulation() -> None:
    records = parse_smoke_report(SMOKE_REPORT)
    print(f"Parsed {len(records)} records", file=sys.stderr)
    results = [_select_new(r) for r in records]
    path = write_report(records, results)
    print(f"Report: {path}", file=sys.stderr)


# FUNCTIONS

# Select best snippet under new logic; returns (source, raw_text, score, clean_len, floor_triggered) or None
def _select_new(record: dict):
    candidates = {}
    if record["og"]:   candidates["og"]   = record["og"]
    if record["meta"]: candidates["meta"] = record["meta"]
    for eng, text in record["snippets"].items():
        if text: candidates[eng] = text

    if not candidates:
        return None

    scored = {}
    for src, text in candidates.items():
        clean_len = len(strip_bloat(text))
        score     = clean_len * lexical_density(text)
        scored[src] = (score, clean_len)

    above_floor     = {s: v for s, v in scored.items() if v[1] >= MIN_FLOOR}
    floor_triggered = len(above_floor) == 0
    pool = above_floor if above_floor else scored

    winner           = max(pool, key=lambda s: pool[s][0])
    score, clean_len = scored[winner]
    return winner, strip_bloat(candidates[winner]), score, clean_len, floor_triggered


# Extract aggregation totals from records × results pairs
def _compute_aggregates(records: list[dict], results: list) -> tuple:
    no_content     = sum(1 for r in results if r is None)
    analyzed       = len(records) - no_content
    floor_records: list[tuple]               = []
    new_dist:      dict[str, int]            = defaultdict(int)
    class_dist:    dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_class_total: dict[str, int]          = defaultdict(int)
    for rec, res in zip(records, results):
        if res is None:
            continue
        new_src, _, _, _, floor_trig = res
        cls = rec.get("class", "GENERAL")
        new_dist[new_src] += 1
        class_dist[new_src][cls] += 1
        per_class_total[cls] += 1
        if floor_trig:
            floor_records.append((rec, res))
    floor_n = len(floor_records)
    return no_content, analyzed, floor_records, new_dist, class_dist, per_class_total, floor_n


# Render report header metadata block
def _render_header(ts: str) -> list[str]:
    return [
        f"# Snippet Selection Simulator — {ts}",
        "",
        f"Source: `{SMOKE_REPORT.name}`  ",
        f"Logic: highest `clean_len × lex_density`; MIN_FLOOR={MIN_FLOOR} chars (best-of-worst if all below).",
        "",
    ]


# Render Section 1 — summary counts and NEW source distribution tables
def _render_summary(new_dist: dict, analyzed: int, no_content: int, floor_n: int,
                    per_class_total: dict, class_dist: dict) -> list[str]:
    L: list[str] = [
        "## 1. Summary",
        "",
        f"- Total URLs analyzed: **{analyzed}** (records with ≥1 non-empty source)  ",
        f"- No-content records (excluded): {no_content}  ",
        f"- Floor-trigger count (best-of-worst fallback): **{floor_n}**  ",
        f"- Per-class: GENERAL {per_class_total['GENERAL']} · ACADEMIC {per_class_total['ACADEMIC']}"
        f" · QA {per_class_total['QA']}",
        "",
        "### NEW Source Distribution",
        "",
        "| Source | Picks | % |",
        "|--------|------:|--:|",
    ]
    for src, cnt in sorted(new_dist.items(), key=lambda x: -x[1]):
        L.append(f"| {src} | {cnt} | {100*cnt/analyzed:.1f}% |")
    all_sources = [s for s, _ in sorted(new_dist.items(), key=lambda x: -x[1])]
    L += [
        "",
        "### Per-Class NEW Source Distribution",
        "",
        "| Source | GENERAL | ACADEMIC | QA |",
        "|--------|--------:|---------:|---:|",
    ]
    for src in all_sources:
        g = class_dist[src].get("GENERAL", 0)
        a = class_dist[src].get("ACADEMIC", 0)
        q = class_dist[src].get("QA", 0)
        L.append(f"| {src} | {g} | {a} | {q} |")
    L.append("")
    return L


# Render Section 2 — per-query pick blocks (source, score, snippet preview)
def _render_per_query_picks(records: list[dict], results: list) -> list[str]:
    L: list[str] = ["## 2. Per-Query Picks", ""]
    prev_qi = None
    for rec, res in zip(records, results):
        qi = rec["_qi"]
        if qi != prev_qi:
            prev_qi = qi
            L += [f"### Q{qi}: {rec['query']}", ""]
        if res is None:
            title_s = (rec.get("title") or "")[:70]
            L += [
                f"**[Pos {rec['_pos']} · {rec['class']}]** {title_s}",
                f"URL: {rec['url']}",
                "_no content_",
                "",
            ]
            continue
        new_src, new_text, new_score, new_cl, floor_trig = res
        title_s   = (rec.get("title") or "")[:70]
        floor_tag = "  ⚠ floor-trigger" if floor_trig else ""
        L += [
            f"**[Pos {rec['_pos']} · {rec['class']}]** {title_s}",
            f"URL: {rec['url']}",
            f"source={new_src}  clean_len={new_cl}  score={new_score:.1f}{floor_tag}",
            f"snippet: `{new_text[:200]}`",
            "",
        ]
    return L


# Render Section 3 — floor-triggered cases (all-below-MIN_FLOOR best-of-worst fallbacks)
def _render_floor_cases(floor_records: list, floor_n: int) -> list[str]:
    if floor_n == 0:
        return ["## 3. Floor-Triggered Cases", "", "No floor-triggers in dataset.", ""]
    L: list[str] = [f"## 3. Floor-Triggered Cases ({floor_n} URLs — best-of-worst fallback)", ""]
    for rec, res in floor_records:
        new_src, new_text, new_score, new_cl, _ = res
        L += [
            f"URL: {rec['url']}",
            f"winner={new_src}  score={new_score:.1f}  clean_len={new_cl}"
            f"  snippet=`{new_text[:120]}`",
            "",
        ]
    return L


# Render and write the markdown report
def write_report(records: list[dict], results: list) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"snippet_selection_{ts}.md"
    no_content, analyzed, floor_records, new_dist, class_dist, per_class_total, floor_n = \
        _compute_aggregates(records, results)
    L = (
        _render_header(ts)
        + _render_summary(new_dist, analyzed, no_content, floor_n, per_class_total, class_dist)
        + _render_per_query_picks(records, results)
        + _render_floor_cases(floor_records, floor_n)
    )
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    run_simulation()
