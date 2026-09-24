# INFRASTRUCTURE
from pathlib import Path

VANILLA_KEY = (0.75, True, "title+snippet")


# FUNCTIONS

def _build_query_section(
    query: str,
    pool: list[dict],
    hard_slot_top: list,
    slot_counts: dict,
    grid_results: list[dict],
    k1_results: list[dict],
    engine_stats: dict,
    total_raw: int,
    fetch_ms: int,
    hardslot_ms: int,
    bm25_total_ms: int,
    classify,
) -> tuple[str, dict]:
    vanilla_entry = next(
        r for r in grid_results
        if (r["cfg"]["b"], r["cfg"]["sw"], r["cfg"]["repr"]) == VANILLA_KEY
    )
    vanilla_urls = {doc["url"] for doc, _ in vanilla_entry["top20"]}
    hs_urls      = {r.url for r in hard_slot_top}

    all_url_sets = [{doc["url"] for doc, _ in r["top20"]} for r in grid_results]
    stable_urls  = set.intersection(*all_url_sets) if all_url_sets else set()

    lines = _section_header(query, pool, total_raw, engine_stats, slot_counts, fetch_ms, hardslot_ms, bm25_total_ms)
    lines += _section_hard_slot(hard_slot_top, classify)
    lines += _section_vanilla(vanilla_entry)
    lines += _section_main_grid(grid_results, vanilla_urls, hs_urls)
    lines += _section_k1(k1_results, vanilla_urls)
    lines += _section_stability(stable_urls)
    lines += _section_differences(hs_urls, vanilla_urls)

    summary = _query_summary(query, pool, total_raw, stable_urls, hs_urls, vanilla_urls, grid_results, k1_results)
    return "\n".join(lines), summary


def _section_header(query: str, pool: list[dict], total_raw: int, engine_stats: dict, slot_counts: dict, fetch_ms: int, hardslot_ms: int, bm25_total_ms: int) -> list[str]:
    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)

    lines = [
        f"## {query}",
        "",
        f"**Raw results:** {total_raw}  ",
        f"**Unique URLs after dedup:** {len(pool)}  ",
        f"**Engines with results ({len(ok_engines)}):** {engine_line}  ",
        f"**Timing:** fetch={fetch_ms}ms, hardslot={hardslot_ms}ms, bm25_total={bm25_total_ms}ms  ",
        f"**Hard-Slot slot counts:** general={slot_counts.get('general', 0)}, "
        f"academic={slot_counts.get('academic', 0)}, qa={slot_counts.get('qa', 0)}",
        "",
    ]
    return lines


def _section_hard_slot(hard_slot_top: list, classify) -> list[str]:
    lines = []
    lines += [
        "### 1. Hard-Slot Baseline (12 General / 6 Academic / 2 QA)",
        "",
        "| # | Class | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, r in enumerate(hard_slot_top, 1):
        engs = r.engines if r.engines else [r.engine]
        lines.append(f"| {i} | {classify(engs)} | {', '.join(engs)} | {r.url[:90]} |")
    lines.append("")
    return lines


def _section_vanilla(vanilla_entry: dict) -> list[str]:
    lines = []
    lines += [
        "### 2. Vanilla BM25 (k1=1.2, b=0.75, stopwords=on, doc_repr=title+snippet)",
        "",
        "| # | Score | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, (doc, score) in enumerate(vanilla_entry["top20"], 1):
        lines.append(f"| {i} | {score:.4f} | {', '.join(doc['engines'])} | {doc['url'][:90]} |")
    lines.append("")
    return lines


def _section_main_grid(grid_results: list[dict], vanilla_urls: set, hs_urls: set) -> list[str]:
    lines = []
    lines += [
        "### 3. Main-Grid Sensitivity (16 configs)",
        "",
        "| b | stopwords | doc_repr | Overlap w/ Vanilla | Overlap w/ Hard-Slot |",
        "|---|-----------|----------|-------------------|---------------------|",
    ]
    for r in grid_results:
        cfg      = r["cfg"]
        top_urls = {doc["url"] for doc, _ in r["top20"]}
        ov_v     = _overlap(top_urls, vanilla_urls)
        ov_hs    = _overlap(top_urls, hs_urls)
        sw_lbl   = "on" if cfg["sw"] else "off"
        lines.append(f"| {cfg['b']} | {sw_lbl} | {cfg['repr']} | {ov_v}/20 | {ov_hs}/20 |")
    lines.append("")
    return lines


def _section_k1(k1_results: list[dict], vanilla_urls: set) -> list[str]:
    lines = []
    lines += [
        "### 4. k1 Sensitivity (b=0.75, sw=on, repr=title+snippet)",
        "",
        "| k1 | Top-20 Overlap with Vanilla |",
        "|----|----------------------------|",
    ]
    for r in k1_results:
        top_urls = {doc["url"] for doc, _ in r["top20"]}
        lines.append(f"| {r['cfg']['k1']} | {_overlap(top_urls, vanilla_urls)}/20 |")
    lines.append("")
    return lines


def _section_stability(stable_urls: set) -> list[str]:
    lines = []
    lines += [
        "### 5. Top-20 Stability across 16 Main-Grid Configs",
        "",
        f"URLs in Top-20 of **all** 16 configs: **{len(stable_urls)}/20**",
        "",
    ]
    return lines


def _section_differences(hs_urls: set, vanilla_urls: set) -> list[str]:
    lines = []
    only_hs      = hs_urls - vanilla_urls
    only_vanilla = vanilla_urls - hs_urls
    overlap_hv   = _overlap(hs_urls, vanilla_urls)

    lines += [
        "### 6. Differences: Hard-Slot vs Vanilla BM25",
        "",
        f"**Overlap:** {overlap_hv}/20  ",
        "",
    ]
    if only_hs:
        lines.append(f"**Only in Hard-Slot ({len(only_hs)}):**")
        for url in sorted(only_hs):
            lines.append(f"- {url[:100]}")
        lines.append("")
    if only_vanilla:
        lines.append(f"**Only in Vanilla BM25 ({len(only_vanilla)}):**")
        for url in sorted(only_vanilla):
            lines.append(f"- {url[:100]}")
        lines.append("")
    if not only_hs and not only_vanilla:
        lines.append("_Lists are identical._")
        lines.append("")
    return lines


def _query_summary(query: str, pool: list[dict], total_raw: int, stable_urls: set, hs_urls: set, vanilla_urls: set, grid_results: list[dict], k1_results: list[dict]) -> dict:
    overlap_hv   = _overlap(hs_urls, vanilla_urls)

    grid_overlaps_v = [_overlap({doc["url"] for doc, _ in r["top20"]}, vanilla_urls) for r in grid_results]
    k1_overlaps_v   = [_overlap({doc["url"] for doc, _ in r["top20"]}, vanilla_urls) for r in k1_results]

    return {
        "query":              query,
        "raw":                total_raw,
        "unique":             len(pool),
        "stability":          len(stable_urls),
        "overlap_vanilla_hs": overlap_hv,
        "min_grid_v":         min(grid_overlaps_v),
        "max_grid_v":         max(grid_overlaps_v),
        "min_k1_v":           min(k1_overlaps_v),
        "max_k1_v":           max(k1_overlaps_v),
    }


def _write_report(
    sections: list[str], summaries: list[dict], path: Path, total_ms: int, top_n: int
) -> None:
    ts = path.stem.replace("bm25_sweep_", "")

    header = "\n".join([
        f"# BM25 Sweep Probe vs Hard-Slot Baseline — {ts}",
        "",
        f"**Queries:** {len(sections)}  ",
        f"**Engines:** 9 default (Scholar dormant)  ",
        f"**BM25 configs:** 16 main grid (b x stopwords x doc_repr, k1=1.2) + 4 k1 sensitivity  ",
        f"**IDF:** uniform 1.0 (TF + length-norm only, uniform IDF via BM25Uniform subclass)  ",
        f"**Vanilla BM25:** k1=1.2, b=0.75, stopwords=on, doc_repr=title+snippet  ",
        f"**Top-N:** {top_n}  ",
        f"**Total wallclock:** {total_ms}ms",
    ])

    summary_lines = [
        "## Global Summary",
        "",
        "| Query | Raw | Unique | Stability (all-16) | Vanilla↔HS | Grid↔Van (min/max) | k1↔Van (min/max) |",
        "|-------|-----|--------|--------------------|-----------|-------------------|-----------------|",
    ]
    for s in summaries:
        q_short = s["query"][:38]
        summary_lines.append(
            f"| {q_short} | {s['raw']} | {s['unique']} | {s['stability']}/20 | "
            f"{s['overlap_vanilla_hs']}/20 | {s['min_grid_v']}-{s['max_grid_v']}/20 | "
            f"{s['min_k1_v']}-{s['max_k1_v']}/20 |"
        )

    all_parts = [header, "\n".join(summary_lines)] + sections
    path.write_text("\n\n---\n\n".join(all_parts), encoding="utf-8")


def _overlap(a: set, b: set) -> int:
    return len(a & b)
