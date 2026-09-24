#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from bm25_sweep_smoke import QUERIES, VANILLA_K1, _bm25_rank, _build_pool
from src.search.browser import close_browser
from src.search.merge import _merge_and_rank
from src.search.search_web import _query_engines_concurrent, _select_engines

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10

COMPARE_CONFIGS = [
    {"name": "Hard-Slot",   "type": "hardslot"},
    {"name": "Vanilla BM25","type": "bm25", "k1": VANILLA_K1, "b": 0.75, "sw": True,  "repr": "title+snippet"},
    {"name": "b=0 extreme", "type": "bm25", "k1": VANILLA_K1, "b": 0.0,  "sw": True,  "repr": "title+snippet"},
    {"name": "b=1 extreme", "type": "bm25", "k1": VANILLA_K1, "b": 1.0,  "sw": True,  "repr": "title+snippet"},
    {"name": "Title3x",     "type": "bm25", "k1": VANILLA_K1, "b": 0.75, "sw": True,  "repr": "title3x"},
]


# ORCHESTRATOR

async def run_probe() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bm25_compare_{ts}.md"

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)

            t0 = time.perf_counter()
            raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
            fetch_ms = round((time.perf_counter() - t0) * 1000)

            pool = _build_pool(raw_results)

            t0 = time.perf_counter()
            config_tops = _rank_all_configs(raw_results, pool, query)
            rank_ms = round((time.perf_counter() - t0) * 1000)

            ok_count = sum(1 for s in engine_stats.values() if s["result_count"] > 0)
            print(
                f"  raw={len(raw_results)}, unique={len(pool)}, ok_engines={ok_count}, "
                f"fetch={fetch_ms}ms, rank={rank_ms}ms",
                file=sys.stderr,
            )
            query_sections.append(
                _build_query_section(query, config_tops, engine_stats, len(raw_results), len(pool), fetch_ms, rank_ms)
            )
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, report_path, total_ms)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Total:  {total_ms}ms", file=sys.stderr)


# FUNCTIONS

def _rank_all_configs(raw_results: list, pool: list[dict], query: str) -> list[dict]:
    results = []
    for cfg in COMPARE_CONFIGS:
        if cfg["type"] == "hardslot":
            ranked, _ = _merge_and_rank(raw_results)
            top10 = [
                {"url": r.url, "engines": r.engines if r.engines else [r.engine], "score": None}
                for r in ranked[:TOP_N]
            ]
        else:
            pairs = _bm25_rank(pool, query, k1=cfg["k1"], b=cfg["b"], use_sw=cfg["sw"], repr_style=cfg["repr"])
            top10 = [{"url": doc["url"], "engines": doc["engines"], "score": score} for doc, score in pairs[:TOP_N]]
        results.append({"name": cfg["name"], "cfg": cfg, "top10": top10})
    return results


def _build_query_section(
    query: str,
    config_tops: list[dict],
    engine_stats: dict,
    total_raw: int,
    unique: int,
    fetch_ms: int,
    rank_ms: int,
) -> str:
    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)

    lines = [
        f"## {query}",
        "",
        f"**Raw:** {total_raw} | **Unique:** {unique} | **Engines ({len(ok_engines)}):** {engine_line}  ",
        f"**Timing:** fetch={fetch_ms}ms, rank={rank_ms}ms",
        "",
    ]

    for ct in config_tops:
        cfg = ct["cfg"]
        if cfg["type"] == "hardslot":
            cfg_label = "Hard-Slot baseline (12 General / 6 Academic / 2 QA)"
        else:
            sw_str = "on" if cfg["sw"] else "off"
            cfg_label = f"k1={cfg['k1']}, b={cfg['b']}, sw={sw_str}, repr={cfg['repr']}"

        lines += [
            f"#### {ct['name']} — {cfg_label}",
            "",
            "| # | Score | Engines | URL |",
            "|---|-------|---------|-----|",
        ]
        for i, item in enumerate(ct["top10"], 1):
            score_str = f"{item['score']:.4f}" if item["score"] is not None else "—"
            lines.append(f"| {i} | {score_str} | {', '.join(item['engines'])} | {item['url'][:90]} |")
        lines.append("")

    return "\n".join(lines)


def _write_report(sections: list[str], path: Path, total_ms: int) -> None:
    ts = path.stem.replace("bm25_compare_", "")
    header = "\n".join([
        f"# BM25 Focused Comparison — Top-10 per Config — {ts}",
        "",
        f"**Queries:** {len(sections)}  ",
        f"**Configs:** Hard-Slot / Vanilla BM25 (b=0.75) / b=0 extreme / b=1 extreme / Title3x  ",
        f"**IDF:** uniform 1.0 (TF + length-norm only)  ",
        f"**Total wallclock:** {total_ms}ms",
    ])
    all_parts = [header] + sections
    path.write_text("\n\n---\n\n".join(all_parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(run_probe())
