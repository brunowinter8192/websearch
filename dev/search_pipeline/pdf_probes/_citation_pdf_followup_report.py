# INFRASTRUCTURE
from collections import defaultdict
from pathlib import Path

from _citation_pdf_followup_config import (
    DOMAIN_CONCURRENCY_CAP, DOMAIN_COURTESY_SLEEP, GLOBAL_MAX_CONNECTIONS, HOP_TIMEOUT, SOURCE_REPORT,
)


# FUNCTIONS

def _write_report(results: list[dict], wall_secs: float, ts: str, report_dir: Path) -> Path:
    path = report_dir / f"citation_pdf_followup_{ts}.md"
    path.write_text("\n".join(_build_report(results, wall_secs, ts)), encoding="utf-8")
    return path


def _build_report(results: list[dict], wall_secs: float, ts: str) -> list[str]:
    lines: list[str] = [f"# Citation PDF Followup Probe — {ts}", ""]
    lines += _section_metadata(results, wall_secs, ts)
    lines += _section_source_domain_table(results)
    lines += _section_pdf_host_table(results)
    lines += _section_pdf_ok_sample(results)
    lines += _section_html_fallback_sample(results)
    lines += _section_per_url_detail(results)
    return lines


def _section_metadata(results: list[dict], wall_secs: float, ts: str) -> list[str]:
    minutes, seconds = divmod(int(wall_secs), 60)
    outcome_counts: dict[str, int] = defaultdict(int)
    for r in results:
        outcome_counts[r["hop2_outcome"]] += 1
    http4xx = sum(v for k, v in outcome_counts.items() if k.startswith("HTTP_4"))
    http5xx = sum(v for k, v in outcome_counts.items() if k.startswith("HTTP_5"))
    downloadable = outcome_counts.get("PDF_OK", 0)
    pct = f"{100 * downloadable / len(results):.1f}%" if results else "0%"

    return [
        "## Section 1 — Run Metadata",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Timestamp | {ts} |",
        f"| Source report | {SOURCE_REPORT} |",
        f"| Input URLs (HTML_HAS_PDF_LINK) | {len(results)} |",
        f"| Concurrency | global_max={GLOBAL_MAX_CONNECTIONS}, per_pdf_host_cap={DOMAIN_CONCURRENCY_CAP} |",
        f"| Timeout | {HOP_TIMEOUT}s per hop |",
        f"| Courtesy sleep | {DOMAIN_COURTESY_SLEEP}s per pdf-host domain slot |",
        f"| Wall clock | {minutes}m {seconds}s |",
        f"| PDF_OK | {outcome_counts.get('PDF_OK', 0)} ({pct} of input) |",
        f"| HTML_FALLBACK | {outcome_counts.get('HTML_FALLBACK', 0)} |",
        f"| HTTP_4xx | {http4xx} |",
        f"| HTTP_5xx | {http5xx} |",
        f"| TIMEOUT | {outcome_counts.get('TIMEOUT', 0)} |",
        f"| EXTRACTION_FAILED | {outcome_counts.get('EXTRACTION_FAILED', 0)} |",
        "",
    ]


def _section_source_domain_table(results: list[dict]) -> list[str]:
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_domain[r["original_domain"]].append(r)

    lines = [
        "## Section 2 — Per-Source-Domain Table (original URL domain)",
        "",
        "| Source Domain | Total | PDF_OK | HTML_FALLBACK | HTTP_4xx | HTTP_5xx | TIMEOUT | EXTRACTION_FAILED | Downloadable % |",
        "|---------------|------:|-------:|-------------:|---------:|---------:|--------:|------------------:|---------------:|",
    ]
    for d in sorted(by_domain, key=lambda x: -len(by_domain[x])):
        recs = by_domain[d]
        c: dict[str, int] = defaultdict(int)
        for r in recs:
            c[r["hop2_outcome"]] += 1
        total = len(recs)
        pdf_ok = c.get("PDF_OK", 0)
        html_fb = c.get("HTML_FALLBACK", 0)
        http4xx = sum(v for k, v in c.items() if k.startswith("HTTP_4"))
        http5xx = sum(v for k, v in c.items() if k.startswith("HTTP_5"))
        timeout = c.get("TIMEOUT", 0)
        extr_fail = c.get("EXTRACTION_FAILED", 0)
        pct = f"{100 * pdf_ok / total:.0f}%"
        lines.append(
            f"| {d} | {total} | {pdf_ok} | {html_fb} | {http4xx} | {http5xx} | {timeout} | {extr_fail} | {pct} |"
        )
    lines.append("")
    return lines


def _section_pdf_host_table(results: list[dict]) -> list[str]:
    by_host: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        host = r["pdf_host_domain"] or "(no citation_pdf_url)"
        by_host[host].append(r)

    lines = [
        "## Section 3 — Per-PDF-Host-Domain Table (citation_pdf_url domain)",
        "",
        "| PDF Host | Total | PDF_OK | HTML_FALLBACK | HTTP_4xx | HTTP_5xx | TIMEOUT | Downloadable % |",
        "|----------|------:|-------:|-------------:|---------:|---------:|--------:|---------------:|",
    ]
    for h in sorted(by_host, key=lambda x: -len(by_host[x])):
        recs = by_host[h]
        c: dict[str, int] = defaultdict(int)
        for r in recs:
            c[r["hop2_outcome"]] += 1
        total = len(recs)
        pdf_ok = c.get("PDF_OK", 0)
        html_fb = c.get("HTML_FALLBACK", 0)
        http4xx = sum(v for k, v in c.items() if k.startswith("HTTP_4"))
        http5xx = sum(v for k, v in c.items() if k.startswith("HTTP_5"))
        timeout = c.get("TIMEOUT", 0)
        pct = f"{100 * pdf_ok / total:.0f}%" if total else "—"
        lines.append(
            f"| {h} | {total} | {pdf_ok} | {html_fb} | {http4xx} | {http5xx} | {timeout} | {pct} |"
        )
    lines.append("")
    return lines


def _section_pdf_ok_sample(results: list[dict]) -> list[str]:
    ok = [r for r in results if r["hop2_outcome"] == "PDF_OK"]
    lines = [
        "## Section 4 — PDF_OK Sample",
        "",
        f"Total PDF_OK: **{len(ok)}**",
        "",
        "| Original URL | citation_pdf_url | Outcome |",
        "|-------------|-----------------|---------|",
    ]
    for r in ok[:20]:
        orig = r["original_url"][:80].replace("|", "%7C")
        pdf = (r["citation_pdf_url"] or "")[:80].replace("|", "%7C")
        lines.append(f"| {orig} | {pdf} | PDF_OK |")
    lines.append("")
    return lines


def _section_html_fallback_sample(results: list[dict]) -> list[str]:
    fb = [r for r in results if r["hop2_outcome"] == "HTML_FALLBACK"]
    lines = [
        "## Section 5 — HTML_FALLBACK Sample",
        "",
        f"Total HTML_FALLBACK: **{len(fb)}**",
        "",
        "| Original URL | citation_pdf_url | Title / Body Preview |",
        "|-------------|-----------------|---------------------|",
    ]
    for r in fb[:20]:
        orig = r["original_url"][:70].replace("|", "%7C")
        pdf = (r["citation_pdf_url"] or "")[:60].replace("|", "%7C")
        preview = (r["hop2_title"] or r["hop2_body_preview"] or "")[:80].replace("|", " ")
        lines.append(f"| {orig} | {pdf} | {preview} |")
    lines.append("")
    return lines


def _section_per_url_detail(results: list[dict]) -> list[str]:
    sorted_results = sorted(results, key=lambda r: (r["original_domain"], r["original_url"]))

    lines = [
        "## Section 6 — Per-URL Detail",
        "",
        "| Source Domain | Original URL | PDF Host | citation_pdf_url | Hop2 Outcome | Hop2 Status | Notes |",
        "|--------------|-------------|----------|-----------------|:------------:|:-----------:|-------|",
    ]
    for r in sorted_results:
        src = r["original_domain"]
        orig = r["original_url"][:70].replace("|", "%7C")
        host = r["pdf_host_domain"] or "—"
        pdf = (r["citation_pdf_url"] or "—")[:60].replace("|", "%7C")
        outcome = r["hop2_outcome"] or "?"
        status = str(r["hop2_status"]) if r["hop2_status"] else "—"
        notes = ""
        if r["hop2_title"]:
            notes = r["hop2_title"][:60].replace("|", " ")
        elif r["hop1_outcome"] and r["hop1_outcome"] != "OK":
            notes = f"hop1={r['hop1_outcome']}"
        lines.append(f"| {src} | {orig} | {host} | {pdf} | {outcome} | {status} | {notes} |")
    lines.append("")
    return lines
