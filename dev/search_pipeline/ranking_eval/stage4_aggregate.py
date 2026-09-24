#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent

MODES = ["general", "pdf", "books", "docs"]

QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]

METHOD_KEYS   = ["c1", "c2", "c2p", "c3"]
METHOD_LABELS = {
    "c1":  "C1 Overlap-Count",
    "c2":  "C2 BM25 vanilla",
    "c2p": "C2' BM25-Capped",
    "c3":  "C3 Cross-Encoder",
}


# ORCHESTRATOR

def run_aggregate(ts_dir: Path, no_oracle: bool) -> None:
    results = []
    for mode in MODES:
        for query in QUERIES:
            result = _load_and_score_pair(ts_dir, mode, query, no_oracle)
            if result is None:
                print(f"  SKIP (files missing): {mode} × {query[:40]}", file=sys.stderr)
                continue
            md_path = _write_query_md(result, ts_dir)
            print(f"  Written: {md_path.name}", file=sys.stderr)
            results.append(result)

    if not results:
        print("ERROR: no pairs found in ts_dir", file=sys.stderr)
        return

    summary_path = _write_summary_md(results, ts_dir)
    print(f"\nSummary: {summary_path}", file=sys.stderr)


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    union  = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def _load_and_score_pair(
    ts_dir: Path, mode: str, query: str, no_oracle: bool
) -> dict | None:
    slug         = _query_slug(query)
    pool_path    = ts_dir / f"{mode}_{slug}_pool.json"
    methods_path = ts_dir / f"{mode}_{slug}_methods.json"
    oracle_path  = ts_dir / f"{mode}_{slug}_oracle.json"

    if not pool_path.exists() or not methods_path.exists():
        return None

    pool_data    = json.loads(pool_path.read_text())
    methods_data = json.loads(methods_path.read_text())

    oracle_data = None
    if not no_oracle and oracle_path.exists():
        oracle_data = json.loads(oracle_path.read_text())
        if oracle_data.get("undersized_pool") and oracle_data.get("pool_size", -1) == 0:
            oracle_data = None

    def _extract_url(item) -> str:
        return item["url"] if isinstance(item, dict) else item

    oracle_urls = [_extract_url(item) for item in oracle_data.get("top_10", [])] if oracle_data else []
    overlaps    = {key: _jaccard(oracle_urls, methods_data.get(key, [])) for key in METHOD_KEYS}

    ps = pool_data.get("pool_sizes", {})
    pool_size = ps.get("filtered_capped", pool_data.get("pool_size", len(pool_data["pool"])))

    return {
        "mode":         mode,
        "query":        query,
        "slug":         slug,
        "pool":         pool_data["pool"],
        "pool_size":    pool_size,
        "methods":      {key: methods_data.get(key, []) for key in METHOD_KEYS},
        "methods_meta": methods_data,
        "oracle_urls":  oracle_urls,
        "oracle_data":  oracle_data,
        "overlaps":     overlaps,
    }


def _write_query_md(result: dict, ts_dir: Path) -> Path:
    mode  = result["mode"]
    slug  = result["slug"]
    query = result["query"]
    path  = ts_dir / f"{mode}_{slug}_eval.md"
    mm    = result["methods_meta"]

    lines = _render_query_header(result, mode, query, mm)
    lines += _render_pool_dump(result)
    lines += _render_oracle_selection(result)
    lines += _render_method_top10s(result, mm)
    lines += _render_comparison(result, mm)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_query_header(result: dict, mode: str, query: str, mm: dict) -> list[str]:
    return [
        f"# Value Eval — {mode} × {query}",
        "",
        f"**Mode:** {mode}  ",
        f"**Query:** {query}  ",
        f"**Pool size (filtered+capped):** {result['pool_size']}  ",
        f"**google_count:** {mm.get('google_count', '?')}  ",
        f"**full_pool:** {mm.get('pool_size', '?')}  "
        f"| **capped_pool:** {mm.get('capped_pool_size', '?')}  ",
        f"**filtered_capped:** {mm.get('filtered_capped_pool_size', '?')}  ",
        "",
    ]


def _render_pool_dump(result: dict) -> list[str]:
    lines = ["## Pool (oracle input — url/title/snippet)", ""]
    for i, m in enumerate(result["pool"], 1):
        title   = (m.get("title")   or "").strip().replace("\n", " ")[:100]
        snippet = (m.get("snippet") or "").strip().replace("\n", " ")[:200]
        lines += [f"{i}. {m['url']}", f"   Title: {title}", f"   Snippet: {snippet}", ""]
    return lines


def _render_oracle_selection(result: dict) -> list[str]:
    lines = ["## Oracle Selection", ""]
    if result["oracle_data"]:
        for i, item in enumerate(result["oracle_data"].get("top_10", []), 1):
            url       = item["url"] if isinstance(item, dict) else item
            rationale = item.get("rationale", "") if isinstance(item, dict) else ""
            lines += [f"{i}. {url}", f"   Rationale: {rationale}", ""]
    else:
        lines += ["_Oracle not yet selected._", ""]
    return lines


def _render_method_top10s(result: dict, mm: dict) -> list[str]:
    lines = ["## C-Method Top-10s", ""]
    for key in METHOD_KEYS:
        urls = result["methods"].get(key, [])
        ms   = mm.get(f"{key}_ms", "?")
        lines.append(f"### {METHOD_LABELS[key]} — {ms}ms")
        lines.append("")
        if urls:
            for i, url in enumerate(urls, 1):
                lines.append(f"{i}. {url}")
        else:
            lines.append("_No results._")
        lines.append("")
    return lines


def _render_comparison(result: dict, mm: dict) -> list[str]:
    lines = ["## Comparison (Oracle vs Methods)", ""]
    if result["oracle_urls"]:
        lines += _comparison_with_oracle(result)
    else:
        lines += _comparison_pool_coverage(result, mm)
    return lines


def _comparison_with_oracle(result: dict) -> list[str]:
    oracle_set = set(result["oracle_urls"])
    lines = [
        "| Method | Jaccard | Oracle URLs captured |",
        "|--------|---------|----------------------|",
    ]
    for key in METHOD_KEYS:
        method_set = set(result["methods"].get(key, []))
        shared     = oracle_set & method_set
        j          = result["overlaps"][key]
        lines.append(
            f"| {METHOD_LABELS[key]} | {j:.3f} | {len(shared)} / {len(oracle_set)} |"
        )
    lines.append("")

    all_method_urls = set(u for key in METHOD_KEYS for u in result["methods"].get(key, []))
    missed = [u for u in result["oracle_urls"] if u not in all_method_urls]
    lines += ["### Oracle URLs missed by all methods", ""]
    if missed:
        for u in missed:
            lines.append(f"- {u}")
    else:
        lines.append("_All oracle URLs captured by at least one method._")
    lines.append("")
    return lines


def _comparison_pool_coverage(result: dict, mm: dict) -> list[str]:
    mps = mm.get("method_pool_sizes", {})
    lines = [
        "| Method | Pool size | Top-10 count | ms |",
        "|--------|-----------|--------------|----|",
    ]
    for key in METHOD_KEYS:
        urls      = result["methods"].get(key, [])
        ms        = mm.get(f"{key}_ms", "?")
        pool_size = mps.get(key, result["pool_size"])
        lines.append(
            f"| {METHOD_LABELS[key]} | {pool_size} | {len(urls)} | {ms} |"
        )
    lines += ["", "_Oracle not yet selected — Jaccard not computed._", ""]
    return lines


def _write_summary_md(results: list[dict], ts_dir: Path) -> Path:
    path       = ts_dir / "eval_summary.md"
    has_oracle = any(r["oracle_urls"] for r in results)

    lines = [
        "# Value Eval Summary",
        "",
        f"**Pairs:** {len(results)} / 16  ",
        f"**Oracle:** {'present' if has_oracle else 'pending (smoke mode)'}  ",
        "",
    ]

    if has_oracle:
        scored = [r for r in results if r["oracle_urls"]]
        lines += _summary_per_mode_table(scored)
        if scored:
            lines += _summary_overall_winner(scored)
            lines += _summary_mode_signals(scored)

    else:
        lines += _summary_smoke_coverage(results)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _summary_per_mode_table(scored: list[dict]) -> list[str]:
    lines = ["## Per-Mode Mean Jaccard", ""]
    header = "| Mode | " + " | ".join(METHOD_LABELS[k] for k in METHOD_KEYS) + " | Winner |"
    sep    = "|------|" + "---|" * len(METHOD_KEYS) + "--------|"
    lines += [header, sep]
    for mode in MODES:
        grp = [r for r in scored if r["mode"] == mode]
        if not grp:
            continue
        means  = {k: sum(r["overlaps"][k] for r in grp) / len(grp) for k in METHOD_KEYS}
        winner = max(means, key=means.get)
        row    = f"| {mode} | " + " | ".join(f"{means[k]:.3f}" for k in METHOD_KEYS)
        row   += f" | **{METHOD_LABELS[winner]}** |"
        lines.append(row)
    lines.append("")
    return lines


def _summary_overall_winner(scored: list[dict]) -> list[str]:
    overall = {k: sum(r["overlaps"][k] for r in scored) / len(scored) for k in METHOD_KEYS}
    winner  = max(overall, key=overall.get)
    lines = [
        "## Overall Winner",
        "",
        "| Method | Mean Jaccard (all pairs) |",
        "|--------|--------------------------|",
    ]
    for k in METHOD_KEYS:
        mark = "  ← **WINNER**" if k == winner else ""
        lines.append(f"| {METHOD_LABELS[k]} | {overall[k]:.3f}{mark} |")
    lines.append("")
    return lines


def _summary_mode_signals(scored: list[dict]) -> list[str]:
    lines = ["## Mode-Specific Signals (margin ≥ 0.10 vs second-best)", ""]
    found_signal = False
    for mode in MODES:
        grp = [r for r in scored if r["mode"] == mode]
        if not grp:
            continue
        means    = {k: sum(r["overlaps"][k] for r in grp) / len(grp) for k in METHOD_KEYS}
        sorted_k = sorted(means, key=means.get, reverse=True)
        margin   = means[sorted_k[0]] - means[sorted_k[1]]
        if margin >= 0.10:
            lines.append(
                f"- **{mode}**: {METHOD_LABELS[sorted_k[0]]} leads by {margin:.3f} "
                f"(vs {METHOD_LABELS[sorted_k[1]]} at {means[sorted_k[1]]:.3f})"
            )
            found_signal = True
    if not found_signal:
        lines.append("_No mode shows a margin ≥ 0.10 between first and second method._")
    lines.append("")
    return lines


def _summary_smoke_coverage(results: list[dict]) -> list[str]:
    lines = ["## Method Coverage (smoke check — no oracle)", ""]
    lines += [
        "| Mode | Query | Pool | C1 | C2 | C2' | C3 |",
        "|------|-------|------|----|----|-----|-----|",
    ]
    for r in results:
        q_short = r["query"][:38]
        counts  = [len(r["methods"].get(k, [])) for k in METHOD_KEYS]
        lines.append(
            f"| {r['mode']} | {q_short} | {r['pool_size']} "
            f"| {counts[0]} | {counts[1]} | {counts[2]} | {counts[3]} |"
        )
    lines.append("")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 4 — Aggregate (value_eval_v2)")
    parser.add_argument("--ts-dir",    required=True,       help="Directory with pool/methods/oracle JSONs")
    parser.add_argument("--no-oracle", action="store_true", help="Skip oracle (smoke mode)")
    args   = parser.parse_args()
    ts_dir = Path(args.ts_dir)
    if not ts_dir.exists():
        sys.exit(f"ERROR: ts_dir does not exist: {ts_dir}")
    run_aggregate(ts_dir=ts_dir, no_oracle=args.no_oracle)
