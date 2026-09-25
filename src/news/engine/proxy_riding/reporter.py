# INFRASTRUCTURE

from datetime import datetime
from pathlib import Path

from src.news.engine.proxy_riding.state import RiderState
from src.news.engine.proxy_riding.metrics import compute_stats
from src.news.engine.proxy_riding.plots import write_cumulative_plot, write_load_hist, write_cf_hist


# ORCHESTRATOR

def write_riding_report(state: RiderState, job_dir: Path, t_job_start: datetime) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    stats = compute_stats(state, t_job_start)
    write_cumulative_plot(job_dir, stats)
    if stats["load_perc"] is not None:
        write_load_hist(job_dir, stats)
    if stats["cf_perc"] is not None:
        write_cf_hist(job_dir, stats)
    _write_md(job_dir, state, stats, t_job_start)


# FUNCTIONS

def _write_md(
    job_dir: Path, state: RiderState, stats: dict, t_job_start: datetime,
) -> None:
    job_id  = t_job_start.strftime("%Y%m%dT%H%M%SZ")
    rw_rate = stats["n_regwall_fetches"] / max(stats["n_total_fetches"], 1)

    lines = _md_header_counts(state, stats, job_id)
    lines += _md_proxy_riding(stats)
    lines += _md_pool_windows(stats)
    lines += _md_regwall(stats, rw_rate)
    lines += _md_connect_fail(stats)
    lines += _md_load_time(stats)
    lines += _md_plots(stats)

    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")


def _md_header_counts(state: RiderState, stats: dict, job_id: str) -> list[str]:
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
        f"| Cooldown policy | {state.cooldown_mgr.policy} |",
        f"| OK | {stats['n_ok']} |",
        f"| Regwall fetches | {stats['n_regwall_fetches']} |",
        f"| Failed / Empty | {stats['n_failed']} |",
        f"| Failed rotations (2-strike) | {stats['n_fail_rotations']} |",
        f"| Connect-fail fetches | {stats['n_connect_fail']} |",
        f"| Total fetches | {stats['n_total_fetches']} |",
        f"| Termination | `{stats['termination']}` |",
        "",
        "## Throughput",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Wall-clock | {_fmt(stats['wall_s'], '.0f', 's')} |",
        f"| Mean s/fetch | {_fmt(stats['mean_s'], '.2f', 's')} |",
        f"| Median s/fetch | {_fmt(stats['median_s'], '.2f', 's')} |",
        f"| OK URLs/min | {_fmt(stats['urls_per_min'], '.1f')} |",
        "",
    ]


def _fmt(v, spec="", unit="") -> str:
    return f"{format(v, spec)}{unit}" if v is not None else "—"


def _md_proxy_riding(stats: dict) -> list[str]:
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
        "## Eligible proxy pool over time",
        "",
        f"Browser-eligible pool (loaded): {stats['pool_total']:,}",
        "",
    ]


def _md_pool_windows(stats: dict) -> list[str]:
    pw = stats["pool_windows"]
    if not pw:
        return ["No samples — run completed before first poll.", ""]
    lines = [
        "| t (min) | min eligible | avg eligible | peak in-cooldown |",
        "|---|---|---|---|",
    ]
    for w in pw:
        t_label = f"{w['window_min']}–{w['window_min'] + 10}"
        lines.append(
            f"| {t_label} | {w['min_eligible']:,} | {w['avg_eligible']:,}"
            f" | {w['peak_cooldown']:,} |"
        )
    lines += [""]
    return lines


def _md_regwall(stats: dict, rw_rate: float) -> list[str]:
    return [
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


def _md_connect_fail(stats: dict) -> list[str]:
    lines    = ["## Connect-fail breakdown", ""]
    cp       = stats["cf_perc"]
    n_cf_tot = len(stats["cf_times"])
    if cp is None:
        lines += [
            f"_Fewer than 2 connect-fail records (n={n_cf_tot}) — distribution not available._",
            "",
        ]
    else:
        lines += [
            f"n = {cp['n']} connect-fail fetches  ·  timeout = {stats['page_timeout_s']:.1f} s",
            "",
            "| Percentile | Elapsed (s) |",
            "|---|---|",
            f"| p50 | {cp['p50']:.3f} |",
            f"| p90 | {cp['p90']:.3f} |",
            f"| p95 | {cp['p95']:.3f} |",
            f"| p99 | {cp['p99']:.3f} |",
            f"| max | {cp['max']:.3f} |",
            "",
        ]
    sc = stats["cf_subtype_counts"]
    if sc:
        lines += ["### Subtypes", "", "| Subtype | Count | Share |", "|---|---|---|"]
        for label in ("page_timeout", "net_timed_out", "proxy_connect", "other"):
            count = sc.get(label, 0)
            if count:
                lines.append(f"| {label} | {count} | {count / max(n_cf_tot, 1):.1%} |")
        lines += [""]
    return lines


def _md_load_time(stats: dict) -> list[str]:
    lines = ["## Success load-time distribution", ""]
    lp = stats["load_perc"]
    if lp is None:
        lines += [
            f"_Fewer than 2 OK fetches (n={len(stats['load_times'])}) — distribution not available._",
            "",
        ]
    else:
        lines += [
            f"n = {lp['n']} OK fetches  ·  timeout = {stats['page_timeout_s']:.1f} s",
            "",
            "| Percentile | Load time (s) |",
            "|---|---|",
            f"| p50 | {lp['p50']:.3f} |",
            f"| p90 | {lp['p90']:.3f} |",
            f"| p95 | {lp['p95']:.3f} |",
            f"| p99 | {lp['p99']:.3f} |",
            f"| max | {lp['max']:.3f} |",
            "",
        ]
    return lines


def _md_plots(stats: dict) -> list[str]:
    lines = ["## Plots", "", "![Cumulative OK](cumulative.png)", ""]
    if stats["cf_perc"] is not None:
        lines += ["![Connect-fail histogram](connect_fail_hist.png)", ""]
    if stats["load_perc"] is not None:
        lines += ["![Success load-time histogram](success_load_hist.png)", ""]
    return lines
