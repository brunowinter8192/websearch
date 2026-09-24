# INFRASTRUCTURE
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _rerank_probe_smoke_config import BM25_B, BM25_K1, BM25_REPR, QUERY_CATEGORIES, RETRIEVE_N


# FUNCTIONS

# Build markdown section for one query
def _build_query_section(query: str, fs: dict, cf: dict) -> str:
    lines = _section_header(query, fs, cf)

    # Config 1 — Hard-Slot
    lines += _table_hard_slot(cf["hs_top"])

    # Config 2 — Filter + BM25
    lines += _table_scored(
        f"### 2. Filter + BM25-only (k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR})",
        "| # | BM25 Score | Engines | URL |",
        "|---|------------|---------|-----|",
        cf["bm25_top"],
    )

    # Config 3 — Embedding-Cosine
    lines += _table_scored(
        f"### 3. Filter + BM25→Top{RETRIEVE_N} + Embedding-Cosine Rerank (Qwen3-Embedding-0.6B)",
        "| # | Cosine | Engines | URL |",
        "|---|--------|---------|-----|",
        cf["embed_top"],
    )

    # Config 4 — Cross-Encoder
    lines += _table_scored(
        f"### 4. Filter + BM25→Top{RETRIEVE_N} + Cross-Encoder Rerank (Qwen3-Reranker-0.6B)",
        "| # | CE Score | Engines | URL |",
        "|---|----------|---------|-----|",
        cf["ce_top"],
    )

    # Config 5 — BM25-Capped
    lines += _table_scored(
        f"### 5. BM25-Capped reference (K={cf['K']}, no filter, no rerank)",
        "| # | BM25 Score | Engines | URL |",
        "|---|------------|---------|-----|",
        cf["capped_top"],
    )

    return "\n".join(lines)


def _section_header(query: str, fs: dict, cf: dict) -> list[str]:
    engine_stats = fs["engine_stats"]
    raw_count = fs["raw_count"]
    filtered_count = fs["filtered_count"]
    removed_count = fs["removed_count"]
    pattern_hist = fs["pattern_hist"]
    unique_count = fs["unique_count"]
    fetch_ms = fs["fetch_ms"]
    slot_counts = cf["slot_counts"]
    K = cf["K"]
    unique_capped = len(cf["capped_pool"])
    n_candidates = len(cf["bm25_candidates"])
    hardslot_ms = cf["hardslot_ms"]
    bm25_ms = cf["bm25_ms"]
    embed_ms = cf["embed_ms"]
    rerank_ms = cf["rerank_ms"]
    capped_ms = cf["capped_ms"]
    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)

    hist_str = ", ".join(f"{p}={c}" for p, c in pattern_hist.most_common()) if pattern_hist else "none"

    lines = [
        f"## {query}",
        "",
        f"**Raw results:** {raw_count} → **After URL filter:** {filtered_count} "
        f"(removed_by_filter={removed_count}, patterns: {hist_str})  ",
        f"**Unique after dedup:** {unique_count}  ",
        f"**Engines with results ({len(ok_engines)}):** {engine_line}  ",
        f"**Hard-Slot slot counts:** general={slot_counts.get('general', 0)}, "
        f"academic={slot_counts.get('academic', 0)}, qa={slot_counts.get('qa', 0)}  ",
        f"**BM25-Capped:** K={K}, unique_capped={unique_capped}  ",
        f"**BM25→top-{RETRIEVE_N} candidates used for embed/rerank:** {n_candidates}  ",
        f"**Timing:** fetch={fetch_ms}ms | hardslot={hardslot_ms}ms | bm25={bm25_ms}ms "
        f"| embed={embed_ms}ms | rerank={rerank_ms}ms | capped={capped_ms}ms",
        "",
    ]
    return lines


def _table_hard_slot(hs_top: list[dict]) -> list[str]:
    lines = []
    lines += [
        f"### 1. Hard-Slot Baseline (12/6/2) — unfiltered raw (production behavior)",
        "",
        "| # | Score | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, item in enumerate(hs_top, 1):
        lines.append(f"| {i} | — | {', '.join(item['engines'])} | {item['url'][:95]} |")
    lines.append("")
    return lines


def _table_scored(heading: str, header_row: str, sep_row: str, items: list[dict]) -> list[str]:
    lines = [
        heading,
        "",
        header_row,
        sep_row,
    ]
    for i, item in enumerate(items, 1):
        lines.append(f"| {i} | {item['score']:.4f} | {', '.join(item['engines'])} | {item['url'][:95]} |")
    lines.append("")
    return lines


# Build per-category latency + pool-stats aggregation block
def _build_category_summary(summaries: list[dict]) -> str:
    cats = _group_by_category(summaries)

    cat_order = ["academic", "product", "technical", "mixed_pathology"]
    lines = _category_latency(cats, cat_order)
    lines += _category_pathology(cats)
    lines += _category_quality(cats, cat_order)
    return "\n".join(lines)


def _group_by_category(summaries: list[dict]) -> dict[str, list[dict]]:
    cats: dict[str, list[dict]] = defaultdict(list)
    for s in summaries:
        cat = QUERY_CATEGORIES.get(s["query"], "unknown")
        cats[cat].append(s)
    return cats


def _category_latency(cats: dict[str, list[dict]], cat_order: list[str]) -> list[str]:
    lines = [
        "## Per-Category Aggregation",
        "",
        "### Latency (averages across queries in category)",
        "",
        "| Category | n | avg_fetch_ms | avg_rerank_ms | avg_embed_ms | avg_pool_unique |",
        "|----------|---|--------------|---------------|--------------|-----------------|",
    ]
    for cat in cat_order:
        grp = cats.get(cat, [])
        if not grp:
            continue
        n = len(grp)
        avg_fetch  = round(sum(s["fetch_ms"]  for s in grp) / n)
        avg_rerank = round(sum(s["rerank_ms"] for s in grp) / n)
        avg_embed  = round(sum(s["embed_ms"]  for s in grp) / n)
        avg_pool   = round(sum(s["unique_after_dedup"] for s in grp) / n)
        lines.append(f"| {cat} | {n} | {avg_fetch} | {avg_rerank} | {avg_embed} | {avg_pool} |")
    lines.append("")
    return lines


def _category_pathology(cats: dict[str, list[dict]]) -> list[str]:
    lines = []
    lines += [
        "### Pathology Markers (mixed_pathology category — URL filter removals + pool size)",
        "",
        "| Query | removed_filter | pool_unique |",
        "|-------|----------------|-------------|",
    ]
    for s in cats.get("mixed_pathology", []):
        q_short = s["query"][:55]
        lines.append(f"| {q_short} | {s['removed_by_filter']} | {s['unique_after_dedup']} |")
    lines.append("")
    return lines


def _category_quality(cats: dict[str, list[dict]], cat_order: list[str]) -> list[str]:
    lines = []
    lines += [
        "### Quality Score Table (fill in post-run eyeball — count topical top-10 per query)",
        "",
        "| Category | Query | Hard-Slot | BM25-only | Embed-Cosine | Cross-Encoder | BM25-Capped |",
        "|----------|-------|-----------|-----------|--------------|---------------|-------------|",
    ]
    for cat in cat_order:
        for s in cats.get(cat, []):
            q_short = s["query"][:45]
            lines.append(f"| {cat} | {q_short} | | | | | |")
    lines += [
        "",
        "**Total (sum):** | | | | | | |",
        "",
    ]
    return lines


# Write full report: global summary + per-query sections
def _write_report(
    sections: list[str],
    summaries: list[dict],
    path: Path,
    total_ms: int,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sum_lines = [
        "# Rerank Probe — URL-Filter + BM25 + Semantic Rerank",
        "",
        f"**Date:** {ts}  ",
        f"**Queries:** {len(summaries)}  ",
        f"**Configs:** Hard-Slot / Filter+BM25 / Filter+BM25→Embed / Filter+BM25→CrossEncoder / BM25-Capped  ",
        f"**BM25 params:** k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR}  ",
        f"**Retrieve-N for reranking:** {RETRIEVE_N}  ",
        f"**Total wallclock:** {total_ms}ms ({total_ms / 1000:.1f}s)",
        "",
        "## Global Latency Summary",
        "",
        "| Query | fetch_ms | hardslot_ms | bm25_ms | embed_ms | rerank_ms | removed_filter | unique |",
        "|-------|----------|-------------|---------|----------|-----------|----------------|--------|",
    ]
    for s in summaries:
        q_short = s["query"][:40]
        sum_lines.append(
            f"| {q_short} | {s['fetch_ms']} | {s['hardslot_ms']} | {s['bm25_ms']} "
            f"| {s['embed_ms']} | {s['rerank_ms']} | {s['removed_by_filter']} | {s['unique_after_dedup']} |"
        )
    sum_lines.append("")

    category_block = _build_category_summary(summaries)

    header = "\n".join(sum_lines)
    path.write_text("\n\n---\n\n".join([header, category_block] + sections), encoding="utf-8")
