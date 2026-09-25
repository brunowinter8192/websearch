#!/usr/bin/env python3
# INFRASTRUCTURE
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from _lib.parse import KNOWN_ENGINES, parse_smoke_report

REPORT_DIR = SCRIPT_DIR / "md"
_smoke_candidates = sorted(REPORT_DIR.glob("pipeline_smoke_*.md"), reverse=True)
if not _smoke_candidates:
    raise FileNotFoundError(f"No pipeline_smoke_*.md found in {REPORT_DIR}")
SMOKE_REPORT = _smoke_candidates[0]

ENGINE_COLUMN_ORDER = [
    "google", "duckduckgo", "mojeek",
    "google_scholar", "openalex", "crossref",
    "stack_exchange", "lobsters",
]

ENGINE_CLASS = {
    "google":         "GENERAL",
    "duckduckgo":     "GENERAL",
    "mojeek":         "GENERAL",
    "google_scholar": "ACADEMIC",
    "openalex":       "ACADEMIC",
    "crossref":       "ACADEMIC",
    "stack_exchange": "QA",
    "lobsters":       "QA",
}

CLASS_ENGINES = {
    "GENERAL":  ["google", "duckduckgo", "mojeek"],
    "ACADEMIC": ["google_scholar", "openalex", "crossref"],
    "QA":       ["stack_exchange", "lobsters"],
}

SHORT = {
    "google":         "google",
    "duckduckgo":     "ddg",
    "mojeek":         "mojeek",
    "google_scholar": "scholar",
    "openalex":       "openalex",
    "crossref":       "crossref",
    "stack_exchange": "stack_ex",
    "lobsters":       "lobsters",
}


# ORCHESTRATOR

def run_analysis() -> None:
    records    = parse_smoke_report(SMOKE_REPORT)
    _print_parsed_records(records)
    slot_counts = compute_slot_counts(records)
    status_agg  = parse_status_aggregate(SMOKE_REPORT)
    baselines   = compute_baselines(slot_counts, status_agg)
    per_query   = compute_per_query_distribution(records)
    path = write_report(records, slot_counts, status_agg, baselines, per_query)
    _print_report(path)


# FUNCTIONS

def _print_parsed_records(records):
    print(f"Parsed {len(records)} records", file=sys.stderr)


def compute_slot_counts(records: list[dict]) -> dict:
    counts = {
        eng: {"total": 0, "GENERAL": 0, "ACADEMIC": 0, "QA": 0, "solo": 0, "overlap": 0}
        for eng in KNOWN_ENGINES
    }
    for rec in records:
        cls   = rec.get("class", "GENERAL")
        known = [e for e in rec["engines"] if e in KNOWN_ENGINES]
        is_solo = len(known) == 1
        for eng in known:
            counts[eng]["total"] += 1
            if cls in counts[eng]:
                counts[eng][cls] += 1
            if is_solo:
                counts[eng]["solo"]    += 1
            else:
                counts[eng]["overlap"] += 1
    return counts


def parse_status_aggregate(path: Path) -> dict:
    lines      = path.read_text(encoding="utf-8").splitlines()
    status: dict[str, dict] = {}
    in_section = False
    for line in lines:
        if line.strip() == "## Per-Engine Status Aggregate":
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("## "):
            break
        m = re.match(r'^\| (\w+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|', line)
        if m:
            status[m.group(1)] = {
                "OK":      int(m.group(2)),
                "EMPTY":   int(m.group(3)),
                "TIMEOUT": int(m.group(4)),
                "ERROR":   int(m.group(5)),
            }
    return status


def compute_baselines(slot_counts: dict, status_agg: dict) -> dict:
    result: dict[str, dict] = {}
    for cls, engines in CLASS_ENGINES.items():
        total_cls = sum(slot_counts[e][cls] for e in engines)
        sum_ok    = sum(status_agg.get(e, {}).get("OK", 0) for e in engines)
        n_engines = len(engines)
        for eng in engines:
            slots   = slot_counts[eng][cls]
            actual  = 100.0 * slots / total_cls if total_cls else 0.0
            uniform = 100.0 / n_engines
            if sum_ok:
                ok_count = status_agg.get(eng, {}).get("OK", 0)
                ok_adj   = 100.0 * ok_count / sum_ok
            else:
                ok_adj = None
            result[eng] = {
                "class":    cls,
                "actual":   actual,
                "uniform":  uniform,
                "ok_adj":   ok_adj,
                "d_uniform": actual - uniform,
                "d_ok_adj":  (actual - ok_adj) if ok_adj is not None else None,
            }
    return result


def compute_per_query_distribution(records: list[dict]) -> list[tuple]:
    qi_query:  dict[int, str]                     = {}
    qi_counts: dict[int, dict[str, int]]           = defaultdict(lambda: defaultdict(int))
    for rec in records:
        qi = rec["_qi"]
        qi_query[qi] = rec["query"]
        for eng in rec["engines"]:
            if eng in KNOWN_ENGINES:
                qi_counts[qi][eng] += 1
    return [(qi, qi_query[qi], dict(qi_counts[qi])) for qi in sorted(qi_query)]


def write_report(
    records:     list[dict],
    slot_counts: dict,
    status_agg:  dict,
    baselines:   dict,
    per_query:   list[tuple],
) -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"engine_distribution_{ts}.md"
    L = (
        _render_header(ts, records, per_query)
        + _render_slot_counts(slot_counts, records, per_query)
        + _render_status_aggregate(status_agg)
        + _render_slot_share(baselines)
        + _render_per_query_distribution(per_query)
    )
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def _print_report(path):
    print(f"Report: {path}", file=sys.stderr)


def _render_header(ts: str, records: list[dict], per_query: list[tuple]) -> list[str]:
    return [
        f"# Engine Distribution Analysis — {ts}",
        "",
        f"Source: `{SMOKE_REPORT.name}`  ",
        f"URL records parsed: {len(records)}  ",
        f"Queries: {len(per_query)}",
        "",
    ]


def _render_slot_counts(slot_counts: dict, records: list[dict], per_query: list[tuple]) -> list[str]:
    n_queries = len(per_query)
    gen_sum  = sum(slot_counts[e]["GENERAL"]  for e in ENGINE_COLUMN_ORDER)
    aca_sum  = sum(slot_counts[e]["ACADEMIC"] for e in ENGINE_COLUMN_ORDER)
    qa_sum   = sum(slot_counts[e]["QA"]       for e in ENGINE_COLUMN_ORDER)
    gen_urls = sum(1 for r in records if r.get("class") == "GENERAL")
    aca_urls = sum(1 for r in records if r.get("class") == "ACADEMIC")
    qa_urls  = sum(1 for r in records if r.get("class") == "QA")
    L: list[str] = [
        "## 1. Per-Engine Slot-Count Total",
        "",
        "Each URL record contributes +1 to every engine listed in its `Engines:` field.  ",
        "Solo = engine is the only known contributor for that URL.  ",
        "Overlap = URL has ≥2 known engine contributors.",
        "",
        "| Engine | Class | Total | GENERAL | ACADEMIC | QA | Solo | Overlap |",
        "|--------|-------|------:|--------:|---------:|---:|-----:|--------:|",
    ]
    for eng in ENGINE_COLUMN_ORDER:
        c   = slot_counts[eng]
        cls = ENGINE_CLASS[eng]
        L.append(
            f"| {eng} | {cls} | {c['total']} | {c['GENERAL']} | {c['ACADEMIC']}"
            f" | {c['QA']} | {c['solo']} | {c['overlap']} |"
        )
    L += [
        "",
        f"Column sums — GENERAL: **{gen_sum}** (URL count {gen_urls} = 12 × {n_queries} queries;"
        f" sum ≥ URL count due to multi-engine overlaps)  ",
        f"ACADEMIC: **{aca_sum}** (URL count {aca_urls})  ",
        f"QA: **{qa_sum}** (URL count {qa_urls})",
        "",
    ]
    return L


def _render_status_aggregate(status_agg: dict) -> list[str]:
    L: list[str] = [
        "## 2. Per-Engine Status Aggregate",
        "",
        f"Quoted through from `{SMOKE_REPORT.name}` — no recomputation.",
        "",
        "| Engine | OK | EMPTY | TIMEOUT | ERROR |",
        "|--------|---:|------:|--------:|------:|",
    ]
    for eng in ENGINE_COLUMN_ORDER:
        s = status_agg.get(eng, {"OK": 0, "EMPTY": 0, "TIMEOUT": 0, "ERROR": 0})
        L.append(f"| {eng} | {s['OK']} | {s['EMPTY']} | {s['TIMEOUT']} | {s['ERROR']} |")
    L.append("")
    return L


def _render_slot_share(baselines: dict) -> list[str]:
    L: list[str] = [
        "## 3. Slot-Share + Baselines",
        "",
        "actual% = engine slot-count in class / total slot-count in class × 100  ",
        "uniform% = 1 / N_engines_in_class × 100 (33.3% GENERAL/ACADEMIC · 50.0% QA)  ",
        "ok_adj% = engine OK count / sum of OK counts in class × 100  ",
        "Δ = actual − baseline (negative = underrepresented · positive = overrepresented)",
        "",
    ]
    for cls in ("GENERAL", "ACADEMIC", "QA"):
        L += [
            f"### {cls}",
            "",
            "| Engine | actual% | uniform% | ok_adj% | Δ_uniform | Δ_ok_adj |",
            "|--------|--------:|---------:|--------:|----------:|---------:|",
        ]
        for eng in CLASS_ENGINES[cls]:
            b      = baselines[eng]
            ok_s   = f"{b['ok_adj']:.1f}"    if b["ok_adj"]   is not None else "—"
            dok_s  = f"{b['d_ok_adj']:+.1f}" if b["d_ok_adj"] is not None else "—"
            L.append(
                f"| {eng} | {b['actual']:.1f} | {b['uniform']:.1f}"
                f" | {ok_s} | {b['d_uniform']:+.1f} | {dok_s} |"
            )
        L.append("")
    return L


def _render_per_query_distribution(per_query: list[tuple]) -> list[str]:
    hdrs = " | ".join(SHORT[e] for e in ENGINE_COLUMN_ORDER)
    seps = "|".join("---:" for _ in ENGINE_COLUMN_ORDER)
    L: list[str] = [
        "## 4. Per-Query Distribution",
        "",
        "Cell = slot-count contributed by that engine in that query.  ",
        "Row sums exceed 20 when GENERAL URLs have multiple contributing engines.",
        "",
        f"| # | Query | {hdrs} | Sum |",
        f"|---|-------|{seps}|----:|",
    ]
    for qi, query, eng_counts in per_query:
        q_short = query[:40]
        cells   = " | ".join(str(eng_counts.get(e, 0)) for e in ENGINE_COLUMN_ORDER)
        row_sum = sum(eng_counts.get(e, 0) for e in ENGINE_COLUMN_ORDER)
        L.append(f"| {qi} | {q_short} | {cells} | {row_sum} |")
    L.append("")
    return L


if __name__ == "__main__":
    run_analysis()
