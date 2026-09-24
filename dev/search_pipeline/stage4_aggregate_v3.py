#!/usr/bin/env python3
"""
Stage 4 v3 — Aggregate (Phase 13, 12-method eval).

Loads pool_v3/*_pool.json + pool_v3/*_methods_v3.json + oracle_dir/*_oracle_v3clean.json,
computes Jaccard per method, writes per-pair eval MD and summary MD into pool_dir.

Summary includes:
  - Per-mode mean Jaccard (12 methods)
  - Per-method latency statistics (mean, p50, p95, max, cold)
  - Quality × Latency Pareto table (DOMINATED flagged)

Usage:
  ./venv/bin/python dev/search_pipeline/stage4_aggregate_v3.py \\
      --pool-dir  dev/search_pipeline/runs/value_eval_v3_<ts> \\
      --oracle-dir dev/search_pipeline/runs/value_eval_v2_20260523_000156 \\
      [--no-oracle]
"""

# INFRASTRUCTURE
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

V2_DEFAULT = SCRIPT_DIR / "runs" / "value_eval_v2_20260523_000156"

MODES = ["general", "pdf", "books", "docs"]
QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]

METHOD_KEYS = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10", "m11", "m12"]
METHOD_LABELS = {
    "m1":  "M1 C1 Overlap-Count",
    "m2":  "M2 RRF post-bucket",
    "m3":  "M3 Structural URL",
    "m4":  "M4 BM25 vanilla",
    "m5":  "M5 BM25-Capped",
    "m6":  "M6 C3 Cross-Encoder",
    "m7":  "M7 C3+InstrPrefix",
    "m8":  "M8 RRF+C3 Hybrid",
    "m9":  "M9 SPLADE",
    "m10": "M10 SPLADE+C3",
    "m11": "M11 C3→LLM-Filter",
    "m12": "M12 LLM-Selector",
}


# ORCHESTRATOR

def run_aggregate_v3(pool_dir: Path, oracle_dir: Path, no_oracle: bool) -> None:
    results = []
    for mode in MODES:
        for query in QUERIES:
            result = _load_and_score_pair(pool_dir, oracle_dir, mode, query, no_oracle)
            if result is None:
                print(f"  SKIP (files missing): {mode} × {query[:40]}", file=sys.stderr)
                continue
            md_path = _write_query_md(result, pool_dir)
            print(f"  Written: {md_path.name}", file=sys.stderr)
            results.append(result)

    if not results:
        print("ERROR: no pairs found", file=sys.stderr)
        return

    summary_path = _write_summary_md(results, pool_dir)
    print(f"\nSummary: {summary_path}", file=sys.stderr)


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    union  = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def _percentile(vals: list[float], p: int) -> float:
    if not vals:
        return 0.0
    sv = sorted(vals)
    idx = int(len(sv) * p / 100)
    return sv[min(idx, len(sv) - 1)]


# Load pool/methods_v3/oracle_v3clean for one pair; compute Jaccard; return result dict or None
def _load_and_score_pair(
    pool_dir: Path, oracle_dir: Path, mode: str, query: str, no_oracle: bool
) -> dict | None:
    slug         = _query_slug(query)
    pool_path    = next(pool_dir.glob(f"{mode}_{slug}*_pool.json"),            None)
    methods_path = next(pool_dir.glob(f"{mode}_{slug}*_methods_v3.json"),      None)
    oracle_path  = next(oracle_dir.glob(f"{mode}_{slug}*_oracle_v3clean.json"), None)

    if pool_path is None or methods_path is None:
        return None

    pool_data    = json.loads(pool_path.read_text())
    methods_data = json.loads(methods_path.read_text())

    oracle_data = None
    if not no_oracle and oracle_path is not None:
        oracle_data = json.loads(oracle_path.read_text())

    oracle_urls = [item["url"] for item in oracle_data.get("top_10", [])] if oracle_data else []
    overlaps    = {k: _jaccard(oracle_urls, methods_data.get(k, [])) for k in METHOD_KEYS}

    ps        = pool_data.get("pool_sizes", {})
    pool_size = ps.get("filtered_capped", len(pool_data["pool"]))

    return {
        "mode":         mode,
        "query":        query,
        "slug":         slug,
        "pool":         pool_data["pool"],
        "pool_size":    pool_size,
        "methods":      {k: methods_data.get(k, []) for k in METHOD_KEYS},
        "methods_meta": methods_data,
        "oracle_urls":  oracle_urls,
        "oracle_data":  oracle_data,
        "overlaps":     overlaps,
    }


# Write per-pair eval MD; return path
def _write_query_md(result: dict, pool_dir: Path) -> Path:
    mode  = result["mode"]
    slug  = result["slug"]
    query = result["query"]
    path  = pool_dir / f"{mode}_{slug}_eval_v3.md"
    mm    = result["methods_meta"]

    lines = [
        f"# Value Eval v3 — {mode} × {query}",
        "",
        f"**Mode:** {mode}  **Query:** {query}  **Pool (filtered):** {mm.get('pool_size_after_filter', '?')}",
        "",
        "## Method Latencies",
        "",
        "| Method | ms |",
        "|--------|-----|",
    ]
    for k in METHOD_KEYS:
        lines.append(f"| {METHOD_LABELS[k]} | {mm.get(f'{k}_ms', '?')} |")
    lines.append("")

    if result["oracle_urls"]:
        oracle_set = set(result["oracle_urls"])
        lines += [
            "## Jaccard vs Oracle (v3clean)",
            "",
            "| Method | Jaccard | Oracle captured |",
            "|--------|---------|-----------------|",
        ]
        for k in METHOD_KEYS:
            method_set = set(result["methods"].get(k, []))
            shared     = oracle_set & method_set
            j          = result["overlaps"][k]
            lines.append(f"| {METHOD_LABELS[k]} | {j:.3f} | {len(shared)}/{len(oracle_set)} |")
        lines.append("")
    else:
        lines += ["_Oracle not yet selected._", ""]

    lines += ["## Pool (oracle input — url/title/snippet)", ""]
    for i, m in enumerate(result["pool"], 1):
        t = (m.get("title")   or "").strip().replace("\n", " ")[:100]
        s = (m.get("snippet") or "").strip().replace("\n", " ")[:200]
        lines += [f"{i}. {m['url']}", f"   {t}", f"   {s}", ""]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# Write summary eval MD with Jaccard + latency sections; return path
def _write_summary_md(results: list[dict], pool_dir: Path) -> Path:
    path       = pool_dir / "eval_summary_v3.md"
    has_oracle = any(r["oracle_urls"] for r in results)
    scored     = [r for r in results if r["oracle_urls"]] if has_oracle else []

    lines = [
        "# Value Eval Summary v3 — 12-Method Phase 13",
        "",
        f"**Pairs:** {len(results)} / 16  **Oracle:** {'v3clean' if has_oracle else 'pending'}",
        "",
    ]

    overall = None
    if has_oracle and scored:
        lines += _summary_per_mode_jaccard(scored)
        overall = {k: sum(r["overlaps"][k] for r in scored) / len(scored) for k in METHOD_KEYS}
        lines += _summary_overall_jaccard(overall)

    lines += _summary_per_mode_latency(results)
    lines += _summary_latency_statistics(results)

    if has_oracle and scored:
        lines += _summary_pareto(results, overall)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _summary_per_mode_jaccard(scored: list[dict]) -> list[str]:
    # Per-mode Jaccard table
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


def _summary_overall_jaccard(overall: dict) -> list[str]:
    # Overall mean Jaccard
    winner  = max(overall, key=overall.get)
    lines = ["## Overall Mean Jaccard", "", "| Method | Mean Jaccard |", "|--------|--------------|"]
    for k in METHOD_KEYS:
        mark = "  ← **WINNER**" if k == winner else ""
        lines.append(f"| {METHOD_LABELS[k]} | {overall[k]:.3f}{mark} |")
    lines.append("")
    return lines


def _summary_per_mode_latency(results: list[dict]) -> list[str]:
    # Per-mode mean latency
    lines = ["## Per-Mode Mean Latency (ms)", ""]
    header = "| Mode | " + " | ".join(k.upper() for k in METHOD_KEYS) + " |"
    sep    = "|------|" + "---|" * len(METHOD_KEYS)
    lines += [header, sep]
    for mode in MODES:
        grp = [r for r in results if r["mode"] == mode]
        if not grp:
            continue
        ms_means = {k: sum(r["methods_meta"].get(f"{k}_ms", 0) for r in grp) / len(grp) for k in METHOD_KEYS}
        row = f"| {mode} | " + " | ".join(f"{ms_means[k]:.0f}" for k in METHOD_KEYS) + " |"
        lines.append(row)
    lines.append("")
    return lines


def _summary_latency_statistics(results: list[dict]) -> list[str]:
    # Per-method latency statistics across all 16 queries
    lines = ["## Per-Method Latency Statistics (across 16 pairs)", ""]
    lines += [
        "| Method | Mean | p50 | p95 | Max | Tokens in/out (LLM) |",
        "|--------|------|-----|-----|-----|---------------------|",
    ]
    for k in METHOD_KEYS:
        ms_vals = [r["methods_meta"].get(f"{k}_ms", 0) for r in results]
        mean_ms = sum(ms_vals) / len(ms_vals) if ms_vals else 0
        p50     = _percentile(ms_vals, 50)
        p95     = _percentile(ms_vals, 95)
        max_ms  = max(ms_vals) if ms_vals else 0
        if k in ("m11", "m12"):
            ti = sum(r["methods_meta"].get(f"{k}_tokens_in", 0)  for r in results)
            to = sum(r["methods_meta"].get(f"{k}_tokens_out", 0) for r in results)
            tok = f"{ti}/{to}"
        else:
            tok = "—"
        lines.append(f"| {METHOD_LABELS[k]} | {mean_ms:.0f} | {p50:.0f} | {p95:.0f} | {max_ms} | {tok} |")
    lines.append("")
    return lines


def _summary_pareto(results: list[dict], overall: dict) -> list[str]:
    # Quality × Latency Pareto
    lines = ["## Quality × Latency Pareto", ""]
    method_stats: list[tuple[str, float, float]] = []
    for k in METHOD_KEYS:
        mean_j  = overall[k]
        ms_vals = [r["methods_meta"].get(f"{k}_ms", 0) for r in results]
        mean_ms = sum(ms_vals) / len(ms_vals) if ms_vals else 0
        method_stats.append((k, mean_j, mean_ms))
    method_stats.sort(key=lambda x: -x[1])  # sort by quality desc

    lines += [
        "| Method | Mean Jaccard | Mean Latency (ms) | Pareto Status |",
        "|--------|--------------|-------------------|---------------|",
    ]
    for k, j, ms in method_stats:
        dominated = any(
            other_j >= j and other_ms <= ms and (other_j > j or other_ms < ms)
            for _, other_j, other_ms in method_stats
            if _ != k
        )
        status = "DOMINATED" if dominated else "Pareto-optimal"
        lines.append(f"| {METHOD_LABELS[k]} | {j:.3f} | {ms:.0f} | {status} |")
    lines.append("")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 4 v3 — Aggregate (Phase 13)")
    parser.add_argument("--pool-dir",   required=True,        help="Directory with *_pool.json + *_methods_v3.json")
    parser.add_argument("--oracle-dir", default=str(V2_DEFAULT), help="Directory with *_oracle_v3clean.json")
    parser.add_argument("--no-oracle",  action="store_true",  help="Skip oracle (smoke mode)")
    args       = parser.parse_args()
    pool_dir   = Path(args.pool_dir)
    oracle_dir = Path(args.oracle_dir)
    for p in (pool_dir, oracle_dir):
        if not p.exists():
            sys.exit(f"ERROR: directory does not exist: {p}")
    run_aggregate_v3(pool_dir=pool_dir, oracle_dir=oracle_dir, no_oracle=args.no_oracle)
