#!/usr/bin/env python3
# INFRASTRUCTURE
import html
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median as stat_median

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from _lib.parse import KNOWN_ENGINES, parse_smoke_report
from _lib.text  import strip_bloat, lexical_density, detect_bloat

REPORT_DIR   = SCRIPT_DIR / "md"
ALL_SOURCES = [
    "og", "meta",
    "google", "duckduckgo", "mojeek", "lobsters",
    "google_scholar", "scholar_strip", "openalex", "crossref", "stack_exchange",
]

MATRIX_ENGINES = [
    "google", "duckduckgo", "mojeek", "lobsters",
    "google_scholar", "openalex", "crossref", "stack_exchange",
]


# ORCHESTRATOR

def run_analysis() -> None:
    smoke_report = _latest_smoke_report()
    records = parse_smoke_report(smoke_report)
    n_s = _compute_sample_count(records)
    n_og = _compute_og_count(records)
    n_m = _compute_meta_count(records)
    _print_parsed_records_snippets(records, n_s, n_og, n_m)
    source_stats       = compute_source_stats(records)
    overlap            = compute_overlap_matrix(records)
    wins, best_per_url = compute_best_by_usefulness(records)
    breakdown          = compute_per_class_breakdown(records, best_per_url)
    path = write_report(source_stats, overlap, records, wins, best_per_url, breakdown)
    _print_report(path)
    _print_source_stats(source_stats)
    total_wins = sum(wins.values())
    _print_best_by_usefulness(total_wins)
    _print_win_shares(wins, total_wins)


# FUNCTIONS

def _compute_sample_count(records):
    n_s  = sum(len(r["snippets"]) for r in records)
    return n_s


def _compute_og_count(records):
    n_og = sum(1 for r in records if r["og"])
    return n_og


def _compute_meta_count(records):
    n_m  = sum(1 for r in records if r["meta"])
    return n_m


def _print_parsed_records_snippets(records, n_s, n_og, n_m):
    print(f"Parsed {len(records)} records  snippets:{n_s}  og:{n_og}  meta:{n_m}", file=sys.stderr)


def compute_source_stats(records: list[dict]) -> dict:
    texts_by, total_by, empty_by = _collect_source_texts(records)
    return {src: _source_stat(src, texts_by, total_by, empty_by) for src in ALL_SOURCES}


def compute_overlap_matrix(records: list[dict]) -> dict:
    url_engines: dict[tuple, set] = defaultdict(set)
    matrix_set = set(MATRIX_ENGINES)
    for rec in records:
        key = (rec["url"], rec["query"])
        for eng in rec["engines"]:
            e = eng.strip().lower()
            if e in matrix_set:
                url_engines[key].add(e)
    matrix: dict[tuple, int] = defaultdict(int)
    for engines in url_engines.values():
        eng_list = sorted(engines)
        for a in range(len(eng_list)):
            for b in range(a + 1, len(eng_list)):
                matrix[(eng_list[a], eng_list[b])] += 1
                matrix[(eng_list[b], eng_list[a])] += 1
    return matrix


def compute_best_by_usefulness(records: list[dict]) -> tuple[dict, dict]:
    wins: dict[str, int]           = defaultdict(int)
    best_per_url: dict[tuple, str] = {}
    for rec in records:
        candidates: dict[str, float] = {}
        for eng, text in rec["snippets"].items():
            if text:
                candidates[eng] = _usefulness(text)
        if rec["og"]:
            candidates["og"]   = _usefulness(rec["og"])
        if rec["meta"]:
            candidates["meta"] = _usefulness(rec["meta"])
        key = (rec["query"], rec["url"])
        if not candidates:
            best_per_url[key] = "empty"
            continue
        winner = max(candidates, key=candidates.__getitem__)
        wins[winner] += 1
        best_per_url[key] = winner
    return dict(wins), best_per_url


def compute_per_class_breakdown(records: list[dict], best_per_url: dict) -> dict:
    breakdown: dict[str, dict[str, int]] = {
        "GENERAL":  defaultdict(int),
        "ACADEMIC": defaultdict(int),
        "QA":       defaultdict(int),
    }
    for rec in records:
        key    = (rec["query"], rec["url"])
        winner = best_per_url.get(key, "empty")
        cls    = rec.get("class", "GENERAL")
        if cls in breakdown:
            breakdown[cls][winner] += 1
    return {k: dict(v) for k, v in breakdown.items()}


def write_report(
    stats: dict, overlap: dict, records: list[dict],
    wins: dict, best_per_url: dict, breakdown: dict,
) -> Path:
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    path       = REPORT_DIR / f"snippet_quality_{ts}.md"
    total_wins = sum(wins.values())
    n_urls     = len(records)
    L = (
        _render_header(ts, n_urls, total_wins)
        + _render_source_stats(stats)
        + _render_overlap_matrix(overlap)
        + _render_winners(wins, total_wins, n_urls)
        + _render_per_class_breakdown(breakdown)
        + _render_url_details(records, best_per_url)
    )
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def _print_report(path):
    print(f"Report: {path}", file=sys.stderr)


def _print_source_stats(source_stats):
    for src, st in source_stats.items():
        print(
            f"  {src}: N={st['n_samples']} bloated={st['pct_bloated']:.0f}%"
            f" clean={st['mean_clean_len']:.0f} useful={st['usefulness_score']:.0f}",
            file=sys.stderr,
        )


def _print_best_by_usefulness(total_wins):
    print(f"\nBest-by-usefulness ({total_wins} URLs with content):", file=sys.stderr)


def _print_win_shares(wins, total_wins):
    for src, w in sorted(wins.items(), key=lambda x: -x[1]):
        print(f"  {src}: {w} ({100.0 * w / total_wins:.1f}%)", file=sys.stderr)


def _collect_source_texts(records: list[dict]) -> tuple[dict, dict, dict]:
    texts_by: dict[str, list[str]] = {s: [] for s in ALL_SOURCES}
    total_by: dict[str, int]       = defaultdict(int)
    empty_by: dict[str, int]       = defaultdict(int)

    for rec in records:
        for eng, text in rec["snippets"].items():
            k = eng.lower()
            if k not in texts_by:
                continue
            total_by[k] += 1
            if text:
                texts_by[k].append(text)
                if k == "google_scholar":
                    stripped = strip_bloat(html.unescape(text))
                    total_by["scholar_strip"] += 1
                    if stripped:
                        texts_by["scholar_strip"].append(stripped)
                    else:
                        empty_by["scholar_strip"] += 1
            else:
                empty_by[k] += 1

        for src, val in (("og", rec["og"]), ("meta", rec["meta"])):
            if val is None:
                continue
            total_by[src] += 1
            if val:
                texts_by[src].append(val)
            else:
                empty_by[src] += 1
    return texts_by, total_by, empty_by


def _source_stat(src: str, texts_by: dict, total_by: dict, empty_by: dict) -> dict:
    txts = texts_by[src]
    n_samples = len(txts)
    if not txts:
        return dict(
            n_total=total_by[src], n_empty=empty_by[src], n_samples=0,
            mean_len=0.0, median_len=0.0, pct_bloated=0.0,
            mean_clean_len=0.0, lexical_density=0.0, usefulness_score=0.0,
        )
    lengths    = [len(t) for t in txts]
    bloated    = [bool(detect_bloat(t)) for t in txts]
    clean_lens = [len(strip_bloat(t)) for t in txts]
    lex        = [lexical_density(t) for t in txts]
    m_clean    = mean(clean_lens)
    m_lex      = mean(lex)
    return dict(
        n_total=total_by[src], n_empty=empty_by[src], n_samples=n_samples,
        mean_len=mean(lengths), median_len=stat_median(lengths),
        pct_bloated=100.0 * sum(bloated) / n_samples,
        mean_clean_len=m_clean,
        lexical_density=m_lex,
        usefulness_score=m_clean * m_lex,
    )


def _usefulness(text: str) -> float:
    if not text:
        return 0.0
    return len(strip_bloat(text)) * lexical_density(text)


def _render_header(ts: str, n_urls: int, total_wins: int) -> list[str]:
    return [
        f"# Snippet Quality Analysis — {ts}",
        "",
        f"Source: `{_latest_smoke_report().name}`  ",
        f"URL records parsed: {n_urls}  ",
        f"URLs with ≥1 non-empty source: {total_wins}",
        "",
    ]


def _render_source_stats(stats: dict) -> list[str]:
    L: list[str] = [
        "## 1. Per-Source Aggregated Stats",
        "",
        "Bloat indicators (any one fires → bloated): "
        "B1 URL breadcrumb (›) · B2 Read-more · B3 Web-results prefix · "
        "B4 Featured-snippet prefix · B5 Social-proof (N likes/comments ·) · "
        "B6 Scholar ellipsis (…) · B7 Mojeek nav-dump (…text…) · "
        "B8 HTML entities · B9 Tag noise · B10 JATS/NS XML tags.  ",
        "Usefulness = mean_clean_len × lexical_density.  ",
        "scholar_strip = google_scholar text after html.unescape + strip_bloat (mirrors _select_snippet Rule 7).",
        "",
        "| Source | N total | N empty | N samples | Mean len | Median len | % bloated | Mean clean len | Lex density | Usefulness |",
        "|--------|---------|---------|-----------|----------|------------|-----------|----------------|-------------|------------|",
    ]
    for src in ALL_SOURCES:
        st = stats[src]
        L.append(
            f"| {src} | {st['n_total']} | {st['n_empty']} | {st['n_samples']}"
            f" | {st['mean_len']:.0f} | {st['median_len']:.0f}"
            f" | {st['pct_bloated']:.0f}% | {st['mean_clean_len']:.0f}"
            f" | {st['lexical_density']:.2f} | {st['usefulness_score']:.0f} |"
        )
    return L


def _render_overlap_matrix(overlap: dict) -> list[str]:
    L: list[str] = [
        "",
        "## 2. Engine Overlap Matrix",
        "",
        "Cell (i, j) = count of (URL, query) pairs where both engines returned the URL.  ",
        "Same URL across different queries counted separately.",
        "",
    ]
    short = {
        "google": "google", "duckduckgo": "ddg", "mojeek": "mojeek",
        "lobsters": "lobsters", "google_scholar": "scholar", "crossref": "crossref",
        "openalex": "openalex", "stack_exchange": "stack_ex",
    }
    L.append("| — | " + " | ".join(short[e] for e in MATRIX_ENGINES) + " |")
    L.append("|---|" + "---|" * len(MATRIX_ENGINES))
    for e1 in MATRIX_ENGINES:
        row = [short[e1]] + [
            "—" if e1 == e2 else str(overlap.get((e1, e2), 0))
            for e2 in MATRIX_ENGINES
        ]
        L.append("| " + " | ".join(row) + " |")
    return L


def _render_winners(wins: dict, total_wins: int, n_urls: int) -> list[str]:
    L: list[str] = [
        "",
        "## 3. Best-by-Usefulness Winners",
        "",
        "Per URL: gather all non-empty sources, compute clean_len × lex_density, pick winner.  ",
        f"Total URLs with ≥1 non-empty source: **{total_wins}** / {n_urls}.  ",
        "This is the empirical answer to: which source produces the best snippet quality?",
        "",
        "| Source | Wins | Win Rate |",
        "|--------|------|----------|",
    ]
    for src, w in sorted(wins.items(), key=lambda x: -x[1]):
        rate = 100.0 * w / total_wins if total_wins else 0.0
        L.append(f"| {src} | {w} | {rate:.1f}% |")
    return L


def _render_per_class_breakdown(breakdown: dict) -> list[str]:
    n_gen = sum(breakdown.get("GENERAL",  {}).values())
    n_ac  = sum(breakdown.get("ACADEMIC", {}).values())
    n_qa  = sum(breakdown.get("QA",       {}).values())
    all_cls_winners = sorted(
        {s for cls_d in breakdown.values() for s in cls_d},
        key=lambda s: -(breakdown.get("GENERAL", {}).get(s, 0)),
    )
    L: list[str] = [
        "",
        "## 4. Per-Class Breakdown",
        "",
        "Win-count from Section 3 split by URL slot class.  ",
        f"GENERAL: {n_gen} URLs · ACADEMIC: {n_ac} URLs · QA: {n_qa} URLs",
        "",
        "| Source | GENERAL | GENERAL% | ACADEMIC | ACADEMIC% | QA | QA% |",
        "|--------|---------|----------|----------|-----------|----|-----|",
    ]
    for src in all_cls_winners:
        g  = breakdown.get("GENERAL",  {}).get(src, 0)
        a  = breakdown.get("ACADEMIC", {}).get(src, 0)
        q  = breakdown.get("QA",       {}).get(src, 0)
        gp = 100.0 * g / n_gen if n_gen else 0.0
        ap = 100.0 * a / n_ac  if n_ac  else 0.0
        qp = 100.0 * q / n_qa  if n_qa  else 0.0
        L.append(f"| {src} | {g} | {gp:.1f}% | {a} | {ap:.1f}% | {q} | {qp:.1f}% |")
    return L


def _render_url_details(records: list[dict], best_per_url: dict) -> list[str]:
    L: list[str] = [
        "",
        "## 5. All URLs — Side-by-Side Snippet Scores",
        "",
        "One block per URL. [winner] = winner (highest clean_len × lex_density).  ",
        "Only non-empty sources shown. Sorted by usefulness descending within each block.",
        "",
    ]
    prev_qi = None
    for rec in records:
        if rec["_qi"] != prev_qi:
            prev_qi = rec["_qi"]
            L += [f"### Q{rec['_qi']}: {rec['query']}", ""]

        key     = (rec["query"], rec["url"])
        winner  = best_per_url.get(key, "empty")
        title_s = (rec.get("title") or "")[:70]

        candidates: dict[str, tuple] = {}
        for eng, text in rec["snippets"].items():
            if text:
                cl = len(strip_bloat(text))
                ld = lexical_density(text)
                candidates[eng] = (cl * ld, cl, ld)
        if rec["og"]:
            cl = len(strip_bloat(rec["og"]))
            ld = lexical_density(rec["og"])
            candidates["og"] = (cl * ld, cl, ld)
        if rec["meta"]:
            cl = len(strip_bloat(rec["meta"]))
            ld = lexical_density(rec["meta"])
            candidates["meta"] = (cl * ld, cl, ld)

        cls = rec.get("class", "?")
        L.append(f"**[Q{rec['_qi']}.{rec['_pos']} · {cls}]** {title_s}")
        L.append(f"URL: {rec.get('url', '')}  ")
        if winner != "empty" and candidates:
            L += [
                "| source | clean_len | lex | useful |",
                "|--------|-----------|-----|--------|",
            ]
            for src, (useful, cl, ld) in sorted(candidates.items(), key=lambda x: -x[1][0]):
                star = " [winner]" if src == winner else ""
                L.append(f"| **{src}**{star} | {cl} | {ld:.2f} | {useful:.0f} |")
        else:
            L.append("*no content*")
        L.append("")
    return L


def _latest_smoke_report() -> Path:
    candidates = sorted(REPORT_DIR.glob("pipeline_smoke_*.md"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No pipeline_smoke_*.md found in {REPORT_DIR}")
    return candidates[0]


if __name__ == "__main__":
    run_analysis()
