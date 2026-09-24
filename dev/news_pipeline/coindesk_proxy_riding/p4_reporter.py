# INFRASTRUCTURE

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p2_browser_rider import RiderState
from _p4_plots import _write_cumulative_plot, _write_ride_length_plot, _write_regwall_position_plot
from _p4_stats import _compute_stats


# ORCHESTRATOR

def write_riding_report(state: RiderState, job_dir: Path, t_job_start: datetime) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    stats = _compute_stats(state, t_job_start)
    _write_cumulative_plot(job_dir, stats)
    _write_ride_length_plot(job_dir, stats)
    _write_regwall_position_plot(job_dir, stats)
    _write_md(job_dir, state, stats, t_job_start)


# FUNCTIONS
def _fmt(v, spec="", unit="") -> str:
    return f"{format(v, spec)}{unit}" if v is not None else "—"


def _render_header_and_counts(job_id: str, state: RiderState, stats: dict) -> list:
    return [
        f"# CoinDesk riding job — {job_id}",
        "",
        "## Counts",
        "",
        "| Status | Count |",
        "|---|---|",
        f"| Target URLs | {state.total_urls} |",
        f"| Browsers | {state.n_browsers} |",
        f"| Contexts/browser | {state.n_slots // max(state.n_browsers, 1)} |",
        f"| OK | {stats['n_ok']} |",
        f"| Regwall fetches | {stats['n_regwall_fetches']} |",
        f"| Failed / Empty | {stats['n_failed']} |",
        f"| Failed rotations (2-strike) | {stats['n_fail_rotations']} |",
        f"| Connect-fail fetches | {stats['n_connect_fail']} |",
        f"| Total fetches | {stats['n_total_fetches']} |",
        f"| Termination | `{stats['termination']}` |",
        "",
    ]


def _render_throughput_section(stats: dict) -> list:
    return [
        "## Throughput",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Wall-clock | {_fmt(stats['wall_s'], '.0f', 's')} |",
        f"| Mean s/fetch | {_fmt(stats['mean_s'], '.2f', 's')} |",
        f"| Median s/fetch | {_fmt(stats['median_s'], '.2f', 's')} |",
        f"| OK URLs/min | {_fmt(stats['urls_per_min'], '.1f')} |",
        f"| Backfill projection (61k) | {_fmt(stats['backfill_h'], '.1f', 'h')} |",
        "",
    ]


def _render_html_size_section(stats: dict) -> list:
    lines = [
        "## HTML size distribution (ok URLs)",
        "",
        "> char_count = len(result.html) — full rendered HTML, typically 300–600 KB.",
        "> Low p50 (< 50k) would indicate truncation or near-empty pages.",
        "",
    ]

    p = stats["html_pct"]
    if p:
        lines += [
            "| Percentile | Chars |",
            "|---|---|",
            f"| p10 | {p['p10']:,} |",
            f"| p25 | {p['p25']:,} |",
            f"| p50 | {p['p50']:,} |",
            f"| p75 | {p['p75']:,} |",
            f"| p90 | {p['p90']:,} |",
            f"| p95 | {p['p95']:,} |",
            "",
        ]
    else:
        lines += ["No ok URLs — skipped.", ""]

    return lines


def _render_markdown_len_section(stats: dict) -> list:
    mp = stats["md_pct"]
    if not mp:
        return []
    return [
        "## Markdown length distribution (ok URLs — body-level signal)",
        "",
        "> markdown_len = len(result.markdown.raw_markdown) — visible rendered text.",
        "> Low p50 (< 5k) despite ok HTML = likely silent regwall or empty body.",
        "",
        "| Percentile | Chars |",
        "|---|---|",
        f"| p10 | {mp['p10']:,} |",
        f"| p25 | {mp['p25']:,} |",
        f"| p50 | {mp['p50']:,} |",
        f"| p75 | {mp['p75']:,} |",
        f"| p90 | {mp['p90']:,} |",
        f"| p95 | {mp['p95']:,} |",
        "",
    ]


def _render_proxy_and_regwall_section(stats: dict, rw_rate: float) -> list:
    rls = stats["ride_len_stats"]
    return [
        "## Proxy riding",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Proxies burned | {stats['n_proxies_burned']} |",
        f"| Rides with ≥1 ok | {sum(1 for c in stats['ride_ok_counts'] if c > 0)} |",
        f"| 61k proxy estimate | {stats['proxies_for_backfill']:,} |",
        "",
        "### Ride length (URLs attempted per proxy)",
        "",
        f"mean={_fmt(rls['mean'], '.1f')}  "
        f"median={_fmt(rls['median'], '.1f')}  "
        f"min={_fmt(rls['min'])}  "
        f"max={_fmt(rls['max'])}",
        "",
        "## Regwall",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Regwall fetches | {stats['n_regwall_fetches']} |",
        f"| Wasted-fetch ratio | {rw_rate:.1%} |",
        f"| URLs with ≥1 regwall | {stats['n_urls_with_regwall']} |",
        f"| → eventually OK | {stats['retried_ok']} |",
        f"| → stayed failed | {stats['retried_failed']} |",
        "",
    ]


def _render_failed_urls_section(job_records: list) -> list:
    failures = [j for j in job_records if j.status == "failed"]
    if not failures:
        return []
    lines = ["## Failed URLs", "", "| URL | Error |", "|---|---|"]
    for j in failures[:20]:
        err = (j.error or "").replace("|", "\\|")[:120]
        lines.append(f"| {j.url[:80]} | {err} |")
    if len(failures) > 20:
        lines.append(f"| … ({len(failures) - 20} more) | |")
    lines.append("")
    return lines


def _render_regwall_urls_section(job_records: list) -> list:
    rw_entries = [j for j in job_records if j.status == "regwall"]
    if not rw_entries:
        return []
    seen_urls: set[str] = set()
    distinct_rw = [j for j in rw_entries if not (j.url in seen_urls or seen_urls.add(j.url))]
    lines = ["## Regwall URLs (distinct)", "", "| URL |", "|---|"]
    for j in distinct_rw[:50]:
        lines.append(f"| {j.url[:100]} |")
    if len(distinct_rw) > 50:
        lines.append(f"| … ({len(distinct_rw) - 50} more) |")
    lines.append("")
    return lines


def _render_plots_section() -> list:
    return [
        "## Plots",
        "",
        "![Cumulative OK](cumulative.png)",
        "",
        "![Ride length distribution](ride_lengths.png)",
        "",
        "![Regwall rate vs position](regwall_position.png)",
        "",
    ]


def _write_md(
    job_dir: Path, state: RiderState, stats: dict, t_job_start: datetime,
) -> None:
    job_id  = t_job_start.strftime("%Y%m%dT%H%M%SZ")
    rw_rate = stats["n_regwall_fetches"] / max(stats["n_total_fetches"], 1)

    lines = []
    lines += _render_header_and_counts(job_id, state, stats)
    lines += _render_throughput_section(stats)
    lines += _render_html_size_section(stats)
    lines += _render_markdown_len_section(stats)
    lines += _render_proxy_and_regwall_section(stats, rw_rate)
    lines += _render_failed_urls_section(state.job_records)
    lines += _render_regwall_urls_section(state.job_records)
    lines += _render_plots_section()

    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")
