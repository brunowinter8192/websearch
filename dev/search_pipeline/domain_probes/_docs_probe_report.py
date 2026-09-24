# INFRASTRUCTURE
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from _docs_probe_config import ENGINE_NAMES, QUERIES, SUFFIX

HEURISTICS: list[tuple[str, str, object]] = [
    ("H1",  "docs subdomain",        lambda h, p: h.startswith("docs.")),
    ("H2",  "readthedocs",           lambda h, p: ".readthedocs.io" in h),
    ("H3",  "gitbook",               lambda h, p: ".gitbook.io" in h),
    ("H4",  "notion-public",         lambda h, p: ".notion.site" in h),
    ("H5",  "developer-subdomain",   lambda h, p: h.startswith("developer.") or h.startswith("developers.")),
    ("H6",  "/docs/ path",           lambda h, p: "/docs/" in p),
    ("H7",  "/documentation/ path",  lambda h, p: "/documentation/" in p),
    ("H8",  "/reference/ path",      lambda h, p: "/reference/" in p),
    ("H9",  "/guide/ path",          lambda h, p: "/guide/" in p),
    ("H10", "/api/ path",            lambda h, p: "/api/" in p),
    ("H11", "/tutorial/ path",       lambda h, p: "/tutorial/" in p),
    ("H12", "/manual/ path",         lambda h, p: "/manual/" in p),
    ("H13", "/learn/ path",          lambda h, p: "/learn/" in p),
]
HEURISTIC_KEYS = [f"{code} — {desc}" for code, desc, _ in HEURISTICS]

TOP_DOMAIN_LIMIT = 30
MIN_DOMAIN_COUNT = 2
TOP_PER_ENGINE = 15
MAX_SAMPLE_PATHS = 3
MAX_PATH_LEN = 80
MISS_SET_MIN = 2


# FUNCTIONS

def write_report(all_runs: dict, run_stats: dict, report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"docs_probe_{ts}.md"
    path.write_text("\n".join(_build_report(all_runs, run_stats, ts)), encoding="utf-8")
    return path


def _build_report(all_runs: dict, run_stats: dict, ts: str) -> list[str]:
    lines = [
        f"# Docs Domain Probe — {ts}",
        "",
        f"**Scope:** {len(QUERIES)} queries × 2 engines × +documentation = {len(QUERIES) * 2} runs",
        "**Engines:** google (max=100), duckduckgo (max=200)",
        "**Modifier:** free word `documentation` appended to each query (no operator)",
        "**Goal:** evaluate H1-H13 heuristics against real URL pool — informs `--docs` whitelist design",
        "**Heuristics:** H1 docs-subdomain · H2 readthedocs · H3 gitbook · H4 notion · H5 developer-subdomain",
        "· H6 /docs/ · H7 /documentation/ · H8 /reference/ · H9 /guide/ · H10 /api/ · H11 /tutorial/ · H12 /manual/ · H13 /learn/",
        "",
    ]
    lines += _section_url_listings(all_runs)
    lines += _section_global_domain_freq(all_runs)
    lines += _section_heuristic_coverage_matrix(all_runs)
    lines += _section_top_n_inspection(all_runs)
    lines += _section_miss_set_analysis(all_runs)
    lines += _section_per_engine_distribution(all_runs)
    lines += _section_run_stats(all_runs, run_stats)
    return lines


def _section_url_listings(all_runs: dict) -> list[str]:
    lines = ["## Per-Query URL Listings", ""]
    for qi, base_query in enumerate(QUERIES, 1):
        results = all_runs.get(base_query, [])
        full_q = f'"{base_query}{SUFFIX}"'
        lines += [
            f"### Q{qi}: {base_query}",
            "",
            f"#### +documentation — {full_q}",
            "",
            "| # | Engine | Pos | URL |",
            "|---|--------|----:|-----|",
        ]
        if results:
            for row_i, r in enumerate(results, 1):
                url = r["url"].replace("|", "%7C")
                lines.append(f"| {row_i} | {r['engine']} | {r['position']} | {url} |")
        else:
            lines.append("| — | — | — | (no results) |")
        lines.append("")
    return lines


def _section_global_domain_freq(all_runs: dict) -> list[str]:
    eng_counters: dict[str, Counter] = {name: Counter() for name in ENGINE_NAMES}
    query_presence: dict[str, set] = defaultdict(set)

    for base_query, results in all_runs.items():
        for r in results:
            d = _domain(r["url"])
            if not d:
                continue
            eng_counters[r["engine"]][d] += 1
            query_presence[d].add(base_query)

    total_counter: Counter = Counter()
    for ec in eng_counters.values():
        total_counter.update(ec)

    above_threshold = [(d, total_counter[d]) for d in total_counter if total_counter[d] >= MIN_DOMAIN_COUNT]
    above_threshold.sort(key=lambda x: x[1], reverse=True)
    singletons = sorted(d for d in total_counter if total_counter[d] < MIN_DOMAIN_COUNT)

    lines = ["## Global Domain Frequency Table", ""]
    lines += [
        f"Domains with count ≥ {MIN_DOMAIN_COUNT} across all {len(QUERIES)} queries and 2 engines.",
        "",
        "| Domain | Total | google | duckduckgo | # Queries |",
        "|--------|------:|------:|-----------:|----------:|",
    ]
    for d, total in above_threshold:
        g = eng_counters["google"][d]
        ddg = eng_counters["duckduckgo"][d]
        nq = len(query_presence[d])
        lines.append(f"| {d} | {total} | {g} | {ddg} | {nq} |")

    lines += [
        "",
        f"**Long tail (count = 1, {len(singletons)} domains):** "
        + (", ".join(singletons[:80]) if singletons else "none"),
        "",
    ]
    if len(singletons) > 80:
        lines.append(f"*(and {len(singletons) - 80} more)*")
        lines.append("")
    return lines




def _section_heuristic_coverage_matrix(all_runs: dict) -> list[str]:
    all_results = [r for results in all_runs.values() for r in results]
    total_urls = len(all_results)

    h_totals, h_eng, none_total, none_eng = _count_heuristic_matches(all_results)

    any_match = total_urls - none_total
    pct_any = round(100 * any_match / total_urls) if total_urls else 0

    lines = ["## Heuristic Coverage Matrix", ""]
    lines += [
        f"Total URL pool: **{total_urls}** URLs ({len(QUERIES)} queries × 2 engines).",
        "A URL may match multiple heuristics — counts are NOT mutually exclusive.",
        "",
        "| Heuristic | Total | % pool | google | duckduckgo |",
        "|-----------|------:|-------:|-------:|-----------:|",
    ]
    for key in HEURISTIC_KEYS:
        t = h_totals[key]
        pct = round(100 * t / total_urls) if total_urls else 0
        g = h_eng[key]["google"]
        ddg = h_eng[key]["duckduckgo"]
        lines.append(f"| {key} | {t} | {pct}% | {g} | {ddg} |")

    pct_none = round(100 * none_total / total_urls) if total_urls else 0
    lines.append(
        f"| **matches NONE** | **{none_total}** | **{pct_none}%** "
        f"| {none_eng['google']} | {none_eng['duckduckgo']} |"
    )
    lines += [
        "",
        f"**Any heuristic match:** {any_match}/{total_urls} ({pct_any}%)",
        "",
    ]
    return lines


def _count_heuristic_matches(all_results: list[dict]) -> tuple[dict, dict, int, dict]:
    h_totals: dict[str, int] = {key: 0 for key in HEURISTIC_KEYS}
    h_eng: dict[str, dict[str, int]] = {
        key: {name: 0 for name in ENGINE_NAMES} for key in HEURISTIC_KEYS
    }
    none_total = 0
    none_eng: dict[str, int] = {name: 0 for name in ENGINE_NAMES}

    for r in all_results:
        matched = _match_heuristics(r["url"])
        if not matched:
            none_total += 1
            none_eng[r["engine"]] += 1
        else:
            for key in matched:
                h_totals[key] += 1
                h_eng[key][r["engine"]] += 1
    return h_totals, h_eng, none_total, none_eng


def _section_top_n_inspection(all_runs: dict) -> list[str]:
    all_results = [r for results in all_runs.values() for r in results]

    total_counter: Counter = Counter()
    domain_paths: dict[str, list[str]] = defaultdict(list)
    seen_paths: dict[str, set] = defaultdict(set)
    domain_hcodes: dict[str, set] = defaultdict(set)

    for r in all_results:
        d = _domain(r["url"])
        if not d:
            continue
        total_counter[d] += 1
        path = urlparse(r["url"]).path
        if path not in seen_paths[d]:
            seen_paths[d].add(path)
            domain_paths[d].append(path[:MAX_PATH_LEN])
        for key in _match_heuristics(r["url"]):
            domain_hcodes[d].add(key.split(" — ")[0])

    top = sorted(total_counter, key=lambda d: total_counter[d], reverse=True)[:TOP_DOMAIN_LIMIT]

    lines = [f"## Top-{TOP_DOMAIN_LIMIT} Domain Inspection", ""]
    lines += [
        "Heuristics column: H-codes matched by ≥1 URL from this domain.",
        "Sample paths are the first distinct URL paths seen. Truncated to 80 chars.",
        "",
        "| Domain | Count | Heuristics | Sample Path 1 | Sample Path 2 | Sample Path 3 |",
        "|--------|------:|:-----------|---------------|---------------|---------------|",
    ]
    for d in top:
        count = total_counter[d]
        paths = domain_paths[d][:MAX_SAMPLE_PATHS]
        row_paths = [f"`{p}`" if p else "`/`" for p in paths]
        while len(row_paths) < MAX_SAMPLE_PATHS:
            row_paths.append("—")
        h_codes = (
            ", ".join(sorted(domain_hcodes[d], key=lambda x: int(x[1:])))
            if domain_hcodes[d] else "—"
        )
        lines.append(
            f"| {d} | {count} | {h_codes} | {row_paths[0]} | {row_paths[1]} | {row_paths[2]} |"
        )
    lines.append("")
    return lines


def _section_miss_set_analysis(all_runs: dict) -> list[str]:
    all_results = [r for results in all_runs.values() for r in results]

    eng_miss: dict[str, Counter] = {name: Counter() for name in ENGINE_NAMES}
    domain_sample: dict[str, str] = {}

    for r in all_results:
        d = _domain(r["url"])
        if not d:
            continue
        if not _match_heuristics(r["url"]):
            eng_miss[r["engine"]][d] += 1
            if d not in domain_sample:
                domain_sample[d] = r["url"]

    total_miss: Counter = Counter()
    for ec in eng_miss.values():
        total_miss.update(ec)

    miss_domains = sorted(
        [(d, total_miss[d]) for d in total_miss if total_miss[d] >= MISS_SET_MIN],
        key=lambda x: x[1], reverse=True,
    )

    lines = ["## Miss Set Analysis", ""]
    lines += [
        f"Domains appearing ≥ {MISS_SET_MIN} times that match **none** of H1-H13.",
        "These are candidates for new heuristics or confirmed noise (non-docs).",
        "",
        "| Domain | Total | google | duckduckgo | Sample URL |",
        "|--------|------:|-------:|-----------:|------------|",
    ]
    if miss_domains:
        for d, total in miss_domains:
            g = eng_miss["google"][d]
            ddg = eng_miss["duckduckgo"][d]
            sample = domain_sample.get(d, "")[:100].replace("|", "%7C")
            lines.append(f"| {d} | {total} | {g} | {ddg} | {sample} |")
    else:
        lines.append("| — | — | — | — | (no miss-set domains at this threshold) |")
    lines.append("")
    return lines


def _section_per_engine_distribution(all_runs: dict) -> list[str]:
    eng_counters: dict[str, Counter] = {name: Counter() for name in ENGINE_NAMES}
    for results in all_runs.values():
        for r in results:
            d = _domain(r["url"])
            if d:
                eng_counters[r["engine"]][d] += 1

    lines = ["## Per-Engine Domain Distribution", ""]
    for eng_name in ENGINE_NAMES:
        ec = eng_counters[eng_name]
        top = ec.most_common(TOP_PER_ENGINE)
        lines += [
            f"### {eng_name} — top {TOP_PER_ENGINE}",
            "",
            "| Domain | Count |",
            "|--------|------:|",
        ]
        for d, cnt in top:
            lines.append(f"| {d} | {cnt} |")
        lines.append("")
    return lines


def _section_run_stats(all_runs: dict, run_stats: dict) -> list[str]:
    lines = ["## Run Stats", ""]
    lines += [
        "| Engine | Total URLs | Mean / Query | Errors / Empties |",
        "|--------|----------:|-------------:|-----------------:|",
    ]
    for eng_name in ENGINE_NAMES:
        total = run_stats[eng_name]["total"]
        errors = run_stats[eng_name]["errors"]
        empties = sum(
            1 for base_query, results in all_runs.items()
            if not any(r["engine"] == eng_name for r in results)
        )
        mean = round(total / len(QUERIES), 1) if QUERIES else 0
        lines.append(f"| {eng_name} | {total} | {mean} | {errors} errors / {empties} empties |")

    total_all = sum(len(v) for v in all_runs.values())
    lines += ["", f"**Total URLs collected:** {total_all}", ""]
    return lines


def _match_heuristics(url: str) -> list[str]:
    try:
        parsed = urlparse(url)
        h = parsed.netloc.lower()
        if h.startswith("www."):
            h = h[4:]
        p = parsed.path
        return [
            HEURISTIC_KEYS[i]
            for i, (_, _, fn) in enumerate(HEURISTICS)
            if fn(h, p)
        ]
    except Exception:
        return []


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""
