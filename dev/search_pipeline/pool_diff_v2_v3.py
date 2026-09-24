#!/usr/bin/env python3
"""
Pool diff — v2 vs v3 reference sets.

Compares URL sets and engine counts for all 16 (mode × query) pairs between
the v2 reference dir and a v3 ts_dir. Writes pool_diff_v2_vs_v3.md.

Usage:
  ./venv/bin/python dev/search_pipeline/pool_diff_v2_v3.py [--v3-dir PATH]
"""

# INFRASTRUCTURE
import argparse
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"
DATA_DIR = SCRIPT_DIR / "runs"

V2_REF = DATA_DIR / "value_eval_v2_20260523_000156"
MODES  = ["general", "pdf", "books", "docs"]
QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]
ENGINES = ["crossref", "duckduckgo", "google", "lobsters", "mojeek",
           "open_library", "openalex", "semantic_scholar", "stack_exchange"]


# ORCHESTRATOR

def pool_diff_workflow(v3_dir: Path) -> None:
    rows     = _compute_rows(v3_dir)
    eng_rows = _compute_engine_rows(v2_dir=V2_REF, v3_dir=v3_dir)
    _write_report(rows, eng_rows, v3_dir)
    out = REPORT_DIR / "pool_diff_v2_vs_v3.md"
    print(out)


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


# Load pool URLs from pool.json; return (set_of_urls, google_count, engine_stat_dict)
def _load_pool(path: Path) -> tuple[set[str], int, dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    urls = {m["url"] for m in d["pool"]}
    google_count = d.get("google_count", 0)
    engine_stats = d.get("engine_stats", {})
    return urls, google_count, engine_stats


# Load engine summary JSON for a ts_dir (engine_report_summary.md has no JSON — read each pool.json)
def _engine_ok_counts(ts_dir: Path) -> dict[str, dict[str, int]]:
    """Return {engine: {ok: N, total: N}} from engine_report.md files — parse pool JSONs instead."""
    # Pool JSONs don't carry engine stats; we rebuild from per-pair pool.json google_count field
    # and from parsing engine_report.md files.
    # Simpler: read engine_report_summary.md text table per ts_dir.
    summary = ts_dir / "engine_report_summary.md"
    if not summary.exists():
        return {}
    lines  = summary.read_text(encoding="utf-8").splitlines()
    result: dict[str, dict[str, int]] = {}
    in_table = False
    for line in lines:
        if line.startswith("| Engine | n |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("| "):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                eng  = parts[1]
                n    = int(parts[2]) if parts[2].isdigit() else 0
                ok   = int(parts[3]) if parts[3].isdigit() else 0
                result[eng] = {"ok": ok, "total": n}
        elif in_table and not line.startswith("|"):
            break
    return result


# Compute per-pair diff rows
def _compute_rows(v3_dir: Path) -> list[dict]:
    rows = []
    for mode in MODES:
        for query in QUERIES:
            slug    = _query_slug(query)
            v2_file = next(V2_REF.glob(f"{mode}_{slug}*_pool.json"), None)
            v3_file = next(v3_dir.glob(f"{mode}_{slug}*_pool.json"), None)
            if v2_file is None or v3_file is None:
                rows.append({
                    "mode": mode, "query": query, "slug": slug,
                    "error": f"missing v2={v2_file is None} v3={v3_file is None}",
                })
                continue
            v2_urls, v2_gc, _ = _load_pool(v2_file)
            v3_urls, v3_gc, _ = _load_pool(v3_file)
            inter = v2_urls & v3_urls
            union = v2_urls | v3_urls
            overlap_pct = round(len(inter) / len(union) * 100, 1) if union else 0.0
            rows.append({
                "mode":        mode,
                "query":       query,
                "slug":        slug,
                "v2_size":     len(v2_urls),
                "v3_size":     len(v3_urls),
                "inter":       len(inter),
                "union":       len(union),
                "new_count":   len(v3_urls - v2_urls),
                "removed":     len(v2_urls - v3_urls),
                "overlap_pct": overlap_pct,
                "v2_gc":       v2_gc,
                "v3_gc":       v3_gc,
            })
    return rows


# Compute per-engine OK% for v2 and v3 from their summary MDs
def _compute_engine_rows(v2_dir: Path, v3_dir: Path) -> list[dict]:
    v2_eng = _engine_ok_counts(v2_dir)
    v3_eng = _engine_ok_counts(v3_dir)
    result = []
    for eng in ENGINES:
        v2 = v2_eng.get(eng, {})
        v3 = v3_eng.get(eng, {})
        def pct(d: dict) -> str:
            return f"{round(d['ok']/d['total']*100)}%" if d.get("total") else "—"
        result.append({
            "engine": eng,
            "v2_ok":  v2.get("ok", 0),
            "v2_n":   v2.get("total", 0),
            "v2_pct": pct(v2),
            "v3_ok":  v3.get("ok", 0),
            "v3_n":   v3.get("total", 0),
            "v3_pct": pct(v3),
        })
    return result


# Write pool_diff_v2_vs_v3.md
def _write_report(rows: list[dict], eng_rows: list[dict], v3_dir: Path) -> None:
    ok_rows  = [r for r in rows if "error" not in r]

    lines = _render_pair_overlap(rows, v3_dir)
    lines += _render_aggregate_stats(ok_rows)
    lines += _render_engine_reliability(eng_rows)
    lines += _render_highlights(ok_rows)

    lines.append("")
    out = REPORT_DIR / "pool_diff_v2_vs_v3.md"
    out.write_text("\n".join(lines), encoding="utf-8")


def _render_pair_overlap(rows: list[dict], v3_dir: Path) -> list[str]:
    lines = [
        "# Pool Diff — v2 vs v3",
        "",
        f"**v2 ref:** `{V2_REF.name}`",
        f"**v3 run:** `{v3_dir.name}`",
        "",
        "## Per-Pair URL Overlap (16 pairs)",
        "",
        "| mode | query (slug) | v2_size | v3_size | overlap_pct | new_in_v3 | removed_from_v2 | v2_google | v3_google |",
        "|------|-------------|---------|---------|-------------|-----------|-----------------|-----------|-----------|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['mode']} | {r['slug']} | — | — | ERROR | — | — | — | — |")
        else:
            lines.append(
                f"| {r['mode']} | {r['slug']} | {r['v2_size']} | {r['v3_size']}"
                f" | {r['overlap_pct']}% | {r['new_count']} | {r['removed']}"
                f" | {r['v2_gc']} | {r['v3_gc']} |"
            )
    return lines


def _render_aggregate_stats(ok_rows: list[dict]) -> list[str]:
    overlaps = [r["overlap_pct"] for r in ok_rows]
    mean_ovl = round(sum(overlaps) / len(overlaps), 1) if overlaps else 0.0
    n_above80 = sum(1 for o in overlaps if o > 80)
    n_below50 = sum(1 for o in overlaps if o < 50)

    return [
        "",
        "## Aggregate Stats",
        "",
        f"- **Mean URL-overlap across 16 pairs:** {mean_ovl}%",
        f"- **Pairs with overlap > 80%:** {n_above80} / {len(ok_rows)}",
        f"- **Pairs with overlap < 50%:** {n_below50} / {len(ok_rows)}",
        "",
    ]


def _render_engine_reliability(eng_rows: list[dict]) -> list[str]:
    lines = [
        "## Per-Engine Reliability (v2 vs v3)",
        "",
        "| Engine | v2 OK | v2 n | v2 OK% | v3 OK | v3 n | v3 OK% |",
        "|--------|-------|------|--------|-------|------|--------|",
    ]
    for e in eng_rows:
        lines.append(
            f"| {e['engine']} | {e['v2_ok']} | {e['v2_n']} | {e['v2_pct']}"
            f" | {e['v3_ok']} | {e['v3_n']} | {e['v3_pct']} |"
        )
    return lines


def _render_highlights(ok_rows: list[dict]) -> list[str]:
    best   = max(ok_rows, key=lambda r: r["overlap_pct"]) if ok_rows else None
    worst  = min(ok_rows, key=lambda r: r["overlap_pct"]) if ok_rows else None
    google_recovered = max(
        (r for r in ok_rows if r["v3_gc"] > r["v2_gc"]),
        key=lambda r: r["v3_gc"] - r["v2_gc"],
        default=None
    )

    lines = ["", "## Highlighted Examples", ""]
    if best:
        lines += [
            f"**Best overlap:** `{best['mode']} × {best['slug']}`"
            f" — {best['overlap_pct']}% ({best['inter']}/{best['union']} URLs shared)",
        ]
    if worst:
        lines += [
            f"**Worst overlap:** `{worst['mode']} × {worst['slug']}`"
            f" — {worst['overlap_pct']}% ({worst['inter']}/{worst['union']} URLs shared)",
        ]
    if google_recovered:
        r = google_recovered
        lines += [
            f"**Most Google-recovered:** `{r['mode']} × {r['slug']}`"
            f" — v2 google_count={r['v2_gc']} → v3 google_count={r['v3_gc']}"
            f" (+{r['v3_gc'] - r['v2_gc']})",
        ]
    elif not any(r.get("v3_gc", 0) > r.get("v2_gc", 0) for r in ok_rows):
        lines += ["**Most Google-recovered:** none — Google CAPTCHA'd in v3 as well (google_count=0 all pairs)"]
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pool diff v2 vs v3")
    parser.add_argument("--v3-dir", default=None, help="v3 ts_dir path (default: latest value_eval_v3_* in runs/)")
    args = parser.parse_args()
    if args.v3_dir:
        v3_dir = Path(args.v3_dir)
    else:
        candidates = sorted(DATA_DIR.glob("value_eval_v3_*"), reverse=True)
        if not candidates:
            raise SystemExit("No value_eval_v3_* dir found in runs/")
        v3_dir = candidates[0]
    pool_diff_workflow(v3_dir)
