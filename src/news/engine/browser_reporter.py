# INFRASTRUCTURE
import statistics
from datetime import datetime, timezone
from pathlib import Path

_BACKFILL_TOTAL = 61_000


# ORCHESTRATOR

def write_scrape_report(
    job_dir: Path,
    job_records: list[dict],
    t_job_start: datetime,
    n_target: int,
    filter_desc: str,
    regwall_abort: bool,
) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    stats = _compute_stats(job_records, t_job_start)
    _write_plot(job_dir, stats)
    _write_md(job_dir, t_job_start, n_target, filter_desc, regwall_abort, job_records, stats)


# FUNCTIONS

def _compute_stats(job_records: list[dict], t_job_start: datetime) -> dict:
    n_ok      = sum(1 for r in job_records if r.get("status") == "ok")
    n_regwall = sum(1 for r in job_records if r.get("status") == "regwall")
    n_empty   = sum(1 for r in job_records if r.get("status") == "empty")
    n_failed  = sum(1 for r in job_records if r.get("status") == "failed")
    n_scraped = len(job_records)

    elapsed_values = [r["elapsed_s"] for r in job_records if r.get("elapsed_s") is not None]
    mean_s   = statistics.mean(elapsed_values)   if elapsed_values else None
    median_s = statistics.median(elapsed_values) if elapsed_values else None

    wall_s = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    urls_per_min = (n_scraped / wall_s * 60) if wall_s > 0 else None
    backfill_h   = (_BACKFILL_TOTAL / urls_per_min / 60) if urls_per_min else None

    ok_chars = sorted(
        r["char_count"] for r in job_records
        if r.get("status") == "ok" and r.get("char_count") is not None
    )
    if len(ok_chars) >= 2:
        qs = statistics.quantiles(ok_chars, n=100, method="inclusive")
        char_pct = {
            "p10": qs[9], "p25": qs[24], "p50": qs[49],
            "p75": qs[74], "p90": qs[89], "p95": qs[94],
        }
    elif len(ok_chars) == 1:
        char_pct = {k: ok_chars[0] for k in ("p10", "p25", "p50", "p75", "p90", "p95")}
    else:
        char_pct = None

    ok_completion_s = sorted(
        (r["t_chunk_start"] - t_job_start).total_seconds() + r["elapsed_s"]
        for r in job_records
        if r.get("status") == "ok" and r.get("elapsed_s") is not None
    )

    return {
        "n_ok": n_ok, "n_regwall": n_regwall, "n_empty": n_empty,
        "n_failed": n_failed, "n_scraped": n_scraped,
        "wall_s": wall_s, "mean_s": mean_s, "median_s": median_s,
        "urls_per_min": urls_per_min, "backfill_h": backfill_h,
        "char_pct": char_pct, "ok_completion_s": ok_completion_s,
    }


def _fmt(v, spec="", unit="") -> str:
    return f"{format(v, spec)}{unit}" if v is not None else "—"


def _write_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    xs = stats["ok_completion_s"]
    if xs:
        x = [0.0] + xs
        y = list(range(len(x)))
    else:
        x, y = [0.0], [0]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.step(x, y, where="post", linewidth=1.5)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Cumulative OK scrapes")
    ax.set_title("Cumulative OK scrapes over time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(job_dir / "cumulative.png", dpi=100)
    plt.close(fig)


def _write_md(
    job_dir: Path,
    t_job_start: datetime,
    n_target: int,
    filter_desc: str,
    regwall_abort: bool,
    job_records: list[dict],
    stats: dict,
) -> None:
    job_id  = t_job_start.strftime("%Y%m%dT%H%M%SZ")
    rw_rate = stats["n_regwall"] / max(stats["n_scraped"], 1)
    rw_cell = f"{stats['n_regwall']} ({rw_rate:.1%})"
    if regwall_abort:
        rw_cell += "  ⚠ **REGWALL ABORT**"

    lines  = _md_header(job_id, filter_desc, n_target, stats, rw_cell)
    lines += _md_char_distribution(stats)
    lines += _md_failure_list(job_records)
    lines += _md_url_list_section("Regwall URLs", job_records, "regwall")
    lines += _md_url_list_section("Empty URLs", job_records, "empty")
    lines += ["![Cumulative OK](cumulative.png)", ""]

    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")


def _md_header(job_id: str, filter_desc: str, n_target: int, stats: dict, rw_cell: str) -> list[str]:
    return [
        f"# Browser scrape job — {job_id}",
        "",
        f"Filter: `{filter_desc}`",
        "",
        "## Counts",
        "",
        "| Status | Count |",
        "|---|---|",
        f"| Target | {n_target} |",
        f"| OK | {stats['n_ok']} |",
        f"| Regwall | {rw_cell} |",
        f"| Empty | {stats['n_empty']} |",
        f"| Failed | {stats['n_failed']} |",
        f"| Total scraped | {stats['n_scraped']} |",
        "",
        "## Throughput",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Wall-clock | {_fmt(stats['wall_s'], '.0f', 's')} |",
        f"| Mean s/URL | {_fmt(stats['mean_s'], '.2f', 's')} |",
        f"| Median s/URL | {_fmt(stats['median_s'], '.2f', 's')} |",
        f"| URLs/min | {_fmt(stats['urls_per_min'], '.1f')} |",
        f"| Backfill projection (61 k) | {_fmt(stats['backfill_h'], '.1f', 'h')} |",
        "",
    ]


def _md_char_distribution(stats: dict) -> list[str]:
    p = stats["char_pct"]
    if not p:
        return ["## Char-count distribution (ok bodies)", "", "No ok bodies — skipped.", ""]
    return [
        "## Char-count distribution (ok bodies)",
        "",
        "| Percentile | Chars | Note |",
        "|---|---|---|",
        f"| p10 | {p['p10']:,} | |",
        f"| p25 | {p['p25']:,} | |",
        f"| p50 | {p['p50']:,} | low p50 ⇒ silent-regwall / truncation risk |",
        f"| p75 | {p['p75']:,} | |",
        f"| p90 | {p['p90']:,} | |",
        f"| p95 | {p['p95']:,} | real articles typically 34 k+ chars |",
        "",
    ]


def _md_failure_list(job_records: list[dict]) -> list[str]:
    failures = [r for r in job_records if r.get("status") == "failed"]
    if not failures:
        return []
    lines = ["## Failure breakdown", "", "| URL | Error |", "|---|---|"]
    for r in failures[:20]:
        err = (r.get("error") or "").replace("|", "\\|")[:120]
        url = (r.get("url") or "")[:80]
        lines.append(f"| {url} | {err} |")
    if len(failures) > 20:
        lines.append(f"| … ({len(failures) - 20} more) | |")
    lines.append("")
    return lines


def _md_url_list_section(title: str, job_records: list[dict], status: str, limit: int = 50) -> list[str]:
    entries = [r for r in job_records if r.get("status") == status]
    if not entries:
        return []
    lines = [f"## {title}", "", "| URL |", "|---|"]
    for r in entries[:limit]:
        lines.append(f"| {(r.get('url') or '')[:100]} |")
    if len(entries) > limit:
        lines.append(f"| … ({len(entries) - limit} more) |")
    lines.append("")
    return lines
