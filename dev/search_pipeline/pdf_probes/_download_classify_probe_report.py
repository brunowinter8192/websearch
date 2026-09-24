# INFRASTRUCTURE
from collections import defaultdict
from pathlib import Path

from _download_classify_probe_pool import _base_domain, RANDOM_SEED
from _download_classify_probe_classify import (
    GLOBAL_MAX_CONNECTIONS, GLOBAL_MAX_KEEPALIVE, DOMAIN_CONCURRENCY_CAP,
    DOMAIN_COURTESY_SLEEP, TIER1_TIMEOUT, DEFAULT_TIMEOUT,
)


# FUNCTIONS

def _write_report(
    results: list[dict],
    sampled_pool: list[tuple[str, str]],
    doi_sample: list[str],
    wall_secs: float,
    smoke_path: Path,
    free_path: Path,
    ts: str,
    report_dir: Path,
) -> Path:
    path = report_dir / f"download_classify_{ts}.md"
    lines = _build_report(results, sampled_pool, doi_sample, wall_secs, smoke_path, free_path, ts)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _build_report(
    results: list[dict],
    sampled_pool: list[tuple[str, str]],
    doi_sample: list[str],
    wall_secs: float,
    smoke_path: Path,
    free_path: Path,
    ts: str,
) -> list[str]:
    lines: list[str] = [f"# Download-Classify Probe — {ts}", ""]

    lines += _section_metadata(results, sampled_pool, doi_sample, wall_secs, smoke_path, free_path, ts)
    lines += _section_domain_aggregate(results)
    lines += _section_tier1_transforms(results)
    lines += _section_html_pdf_link_sample(results)
    lines += _section_paywall_sample(results)
    lines += _section_per_url_detail(results)

    return lines


def _section_metadata(
    results: list[dict],
    sampled_pool: list[tuple[str, str]],
    doi_sample: list[str],
    wall_secs: float,
    smoke_path: Path,
    free_path: Path,
    ts: str,
) -> list[str]:
    total_doi_in_pool = sum(1 for _, t in sampled_pool if t == "T3")
    tier_counts = {t: sum(1 for _, tier in sampled_pool if tier == t) for t in ("T1", "T2", "T3", "T4")}

    outcome_counts: dict[str, int] = defaultdict(int)
    for r in results:
        outcome_counts[r["outcome"]] += 1

    minutes, seconds = divmod(int(wall_secs), 60)

    return [
        "## Section 1 — Run Metadata",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Timestamp | {ts} |",
        f"| Source smoke | {smoke_path.name} |",
        f"| Source free-word | {free_path.name} |",
        f"| Total unique URLs in combined pool (with path) | {len(sampled_pool)} |",
        f"| Tier breakdown | T1={tier_counts.get('T1',0)} T2={tier_counts.get('T2',0)} T3={tier_counts.get('T3',0)} (sampled) T4={tier_counts.get('T4',0)} |",
        f"| doi.org: total in pool | (not probed: full pool has ~2013) |",
        f"| doi.org: sampled | {len(doi_sample)} (seed={RANDOM_SEED}) |",
        f"| doi_sample file | pool_doi_sample_{ts}.txt |",
        f"| Concurrency | global_max={GLOBAL_MAX_CONNECTIONS}, keepalive={GLOBAL_MAX_KEEPALIVE}, per_domain_cap={DOMAIN_CONCURRENCY_CAP} |",
        f"| Timeout | Tier-1={TIER1_TIMEOUT}s, all others={DEFAULT_TIMEOUT}s |",
        f"| Courtesy sleep | {DOMAIN_COURTESY_SLEEP}s per domain slot after request |",
        f"| Wall clock | {minutes}m {seconds}s |",
        f"| Outcomes | PDF_OK={outcome_counts.get('PDF_OK',0)} HTML_HAS_PDF_LINK={outcome_counts.get('HTML_HAS_PDF_LINK',0)} HTML_PAYWALL={outcome_counts.get('HTML_PAYWALL',0)} HTML_OK={outcome_counts.get('HTML_OK',0)} TIMEOUT={outcome_counts.get('TIMEOUT',0)} CONN_ERROR={outcome_counts.get('CONNECTION_ERROR',0)} HTTP_4xx/5xx={sum(v for k,v in outcome_counts.items() if k.startswith('HTTP_'))} |",
        "",
    ]


def _section_domain_aggregate(results: list[dict]) -> list[str]:
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        d = _base_domain(r["original_url"])
        by_domain[d].append(r)

    def _counts(recs: list[dict]) -> dict:
        c: dict[str, int] = defaultdict(int)
        for r in recs:
            c[r["outcome"]] += 1
        return c

    rows = []
    for d in sorted(by_domain, key=lambda x: -len(by_domain[x])):
        recs = by_domain[d]
        c = _counts(recs)
        http4xx = sum(v for k, v in c.items() if k.startswith("HTTP_4"))
        http5xx = sum(v for k, v in c.items() if k.startswith("HTTP_5"))
        rows.append((
            d, len(recs),
            c.get("PDF_OK", 0), c.get("HTML_OK", 0),
            c.get("HTML_HAS_PDF_LINK", 0), c.get("HTML_PAYWALL", 0),
            http4xx, http5xx,
            c.get("TIMEOUT", 0), c.get("CONNECTION_ERROR", 0),
        ))

    lines = [
        "## Section 2 — Per-Domain Aggregate Table",
        "",
        "| Domain | Total | PDF_OK | HTML_OK | HTML_HAS_PDF_LINK | HTML_PAYWALL | HTTP_4xx | HTTP_5xx | TIMEOUT | CONN_ERROR |",
        "|--------|------:|-------:|--------:|------------------:|-------------:|---------:|---------:|--------:|-----------:|",
    ]
    for row in rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} | {row[9]} |")
    lines.append("")
    return lines


def _section_tier1_transforms(results: list[dict]) -> list[str]:
    t1_results = [r for r in results if r["tier"] == "T1"]
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for r in t1_results:
        d = _base_domain(r["original_url"])
        by_domain[d].append(r)

    lines = [
        "## Section 3 — Tier-1 Transform Effectiveness",
        "",
        "| Domain | Applied Transform | PDF_OK | HTML_HAS_PDF_LINK | HTML_OK | HTML_PAYWALL | HTTP_4xx | TIMEOUT | CONN_ERROR |",
        "|--------|:-----------------:|-------:|------------------:|--------:|-------------:|---------:|--------:|-----------:|",
    ]

    for d in sorted(by_domain):
        recs = by_domain[d]
        applied = sum(1 for r in recs if r["transformed_url"] is not None)
        c: dict[str, int] = defaultdict(int)
        for r in recs:
            c[r["outcome"]] += 1
        http4xx = sum(v for k, v in c.items() if k.startswith("HTTP_4"))
        lines.append(
            f"| {d} | {applied}/{len(recs)} | {c.get('PDF_OK',0)} | "
            f"{c.get('HTML_HAS_PDF_LINK',0)} | {c.get('HTML_OK',0)} | "
            f"{c.get('HTML_PAYWALL',0)} | {http4xx} | "
            f"{c.get('TIMEOUT',0)} | {c.get('CONNECTION_ERROR',0)} |"
        )

    lines.append("")
    lines += ["### Tier-1 URL Detail", ""]
    lines += [
        "| Domain | Original URL | Transformed URL | Outcome |",
        "|--------|-------------|-----------------|---------|",
    ]
    for r in sorted(t1_results, key=lambda x: (_base_domain(x["original_url"]), x["original_url"])):
        d = _base_domain(r["original_url"])
        orig = r["original_url"][:80]
        trans = (r["transformed_url"] or "—")[:80]
        lines.append(f"| {d} | {orig} | {trans} | {r['outcome']} |")
    lines.append("")
    return lines


def _section_html_pdf_link_sample(results: list[dict]) -> list[str]:
    pdf_link_results = [r for r in results if r["outcome"] == "HTML_HAS_PDF_LINK"]
    lines = [
        "## Section 4 — HTML_HAS_PDF_LINK Sample",
        "",
        f"Total with citation_pdf_url: **{len(pdf_link_results)}**",
        "",
        "| Original URL | citation_pdf_url |",
        "|-------------|-----------------|",
    ]
    for r in pdf_link_results[:30]:
        orig = r["original_url"][:80].replace("|", "%7C")
        pdf_url = (r["citation_pdf_url"] or "")[:80].replace("|", "%7C")
        lines.append(f"| {orig} | {pdf_url} |")
    lines.append("")
    return lines


def _section_paywall_sample(results: list[dict]) -> list[str]:
    paywall_results = [r for r in results if r["outcome"] == "HTML_PAYWALL"]
    lines = [
        "## Section 5 — HTML_PAYWALL Sample",
        "",
        f"Total with paywall markers: **{len(paywall_results)}**",
        "",
        "| Original URL | Matched Marker |",
        "|-------------|----------------|",
    ]
    for r in paywall_results[:30]:
        orig = r["original_url"][:80].replace("|", "%7C")
        marker = (r["paywall_marker"] or "")
        lines.append(f"| {orig} | `{marker}` |")
    lines.append("")
    return lines


def _section_per_url_detail(results: list[dict]) -> list[str]:
    sorted_results = sorted(results, key=lambda r: (_base_domain(r["original_url"]), r["original_url"]))

    lines = [
        "## Section 6 — Per-URL Detail",
        "",
        "| Domain | Tier | Original URL | Transform? | Final Outcome | Notes |",
        "|--------|------|-------------|:----------:|---------------|-------|",
    ]
    for r in sorted_results:
        d = _base_domain(r["original_url"])
        tier = r["tier"]
        orig = r["original_url"][:70].replace("|", "%7C")
        has_transform = "✓" if r["transformed_url"] else "—"
        outcome = r["outcome"] or "?"

        notes_parts = []
        if r["citation_pdf_url"]:
            notes_parts.append(f"pdf_url={r['citation_pdf_url'][:40]}")
        if r["paywall_marker"]:
            notes_parts.append(f"marker={r['paywall_marker']}")
        if r["page_title"] and outcome in ("CONNECTION_ERROR", "TIMEOUT"):
            notes_parts.append(f"err={r['page_title'][:40]}")
        notes = "; ".join(notes_parts)

        lines.append(f"| {d} | {tier} | {orig} | {has_transform} | {outcome} | {notes} |")
    lines.append("")
    return lines
