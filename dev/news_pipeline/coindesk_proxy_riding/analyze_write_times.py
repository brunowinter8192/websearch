#!/usr/bin/env python3

# INFRASTRUCTURE

import argparse
import os
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_HERE = Path(__file__).resolve()

def _repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=_HERE.parent,
        text=True,
    ).strip()
    p = Path(out)
    return p.parent if p.name in (".git", "worktrees") or ".git" in str(p) else p.parent


_ROOT = _repo_root()
_DEFAULT_RAW_DIR = _ROOT / "data" / "news" / "coindesk" / "raw"
_REPORT_DIR = _HERE.parent / "png"
_POOL_REFRESH_MIN = 30


# ORCHESTRATOR

def main() -> None:
    args   = _parse_args()
    since  = _parse_since(args.since) if args.since else None
    mtimes = _load_mtimes(args.raw_dir, since)
    stats  = _compute_stats(mtimes, args.bin_minutes, args.rolling, args.since)
    _print_summary(stats, args.bin_minutes)
    out    = _plot(stats, args.bin_minutes, args.rolling)
    print(f"PNG: {out}")


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconstruct riding throughput from raw/*.html mtimes.")
    p.add_argument("--raw-dir",     type=Path, default=_DEFAULT_RAW_DIR,
                   help=f"Directory of *.html files (default: {_DEFAULT_RAW_DIR})")
    p.add_argument("--bin-minutes", type=float, default=1.0,
                   help="Bin width for rate histogram in minutes (default: 1)")
    p.add_argument("--rolling",     type=int,   default=5,
                   help="Rolling-mean window in bins (default: 5)")
    p.add_argument("--since",       type=str,   default=None,
                   help="Local timestamp cutoff 'YYYY-MM-DD HH:MM' — exclude mtimes before this")
    return p.parse_args()


def _parse_since(s: str) -> float:
    local_tz = datetime.now().astimezone().tzinfo
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
    return dt.timestamp()


def _load_mtimes(raw_dir: Path, since: float | None) -> list[float]:
    files = list(raw_dir.glob("*.html"))
    if not files:
        raise SystemExit(f"No *.html files found in {raw_dir}")
    mtimes = sorted(os.stat(f).st_mtime for f in files)
    if since is not None:
        before = len(mtimes)
        mtimes = [t for t in mtimes if t >= since]
        print(f"--since filter: {before:,} total → {len(mtimes):,} files after cutoff")
    if not mtimes:
        raise SystemExit("No files remain after --since filter.")
    return mtimes


def _compute_bins(mtimes: list[float], t0: float, span_s: float, bin_minutes: float) -> tuple:
    bin_s    = bin_minutes * 60.0
    n_bins   = int(span_s / bin_s) + 1
    counts   = [0] * n_bins
    for t in mtimes:
        idx = int((t - t0) / bin_s)
        counts[idx] += 1

    bin_starts = [i * bin_minutes for i in range(n_bins)]
    return counts, bin_starts


def _compute_rolling_mean(counts: list, rolling: int) -> list:
    half = rolling // 2
    rolling_mean = []
    for i in range(len(counts)):
        window = counts[max(0, i - half): i + half + 1]
        rolling_mean.append(sum(window) / len(window))
    return rolling_mean


def _compute_rate_stats(counts: list, bin_minutes: float) -> tuple:
    rates_per_min = [c / bin_minutes for c in counts]
    nonzero_rates = [r for r in rates_per_min if r > 0]
    mean_rate   = statistics.mean(nonzero_rates)   if nonzero_rates else 0.0
    median_rate = statistics.median(nonzero_rates) if nonzero_rates else 0.0
    return mean_rate, median_rate


def _compute_longest_gap(mtimes: list[float], t0: float) -> tuple:
    gaps     = [(mtimes[i] - mtimes[i - 1]) for i in range(1, len(mtimes))]
    max_gap_s  = max(gaps)
    max_gap_at = (mtimes[gaps.index(max_gap_s)] - t0) / 60.0
    return max_gap_s, max_gap_at


def _compute_stats(mtimes: list[float], bin_minutes: float, rolling: int, since_label: str | None = None) -> dict:
    t0   = mtimes[0]
    tN   = mtimes[-1]
    span_s = tN - t0

    elapsed_min = [(t - t0) / 60.0 for t in mtimes]

    counts, bin_starts = _compute_bins(mtimes, t0, span_s, bin_minutes)
    rolling_mean = _compute_rolling_mean(counts, rolling)

    cumulative = list(range(1, len(mtimes) + 1))

    mean_rate, median_rate = _compute_rate_stats(counts, bin_minutes)
    max_gap_s, max_gap_at  = _compute_longest_gap(mtimes, t0)

    local_tz = datetime.now().astimezone().tzinfo
    return {
        "n_files":        len(mtimes),
        "span_s":         span_s,
        "elapsed_min":    elapsed_min,
        "cumulative":     cumulative,
        "bin_starts":     bin_starts,
        "counts":         counts,
        "rolling_mean":   rolling_mean,
        "mean_rate":      mean_rate,
        "median_rate":    median_rate,
        "max_gap_s":      max_gap_s,
        "max_gap_at_min": max_gap_at,
        "t0_dt":          datetime.fromtimestamp(mtimes[0],  tz=timezone.utc),
        "tN_dt":          datetime.fromtimestamp(mtimes[-1], tz=timezone.utc),
        "t0_local":       datetime.fromtimestamp(mtimes[0],  tz=local_tz),
        "tN_local":       datetime.fromtimestamp(mtimes[-1], tz=local_tz),
        "since_label":    since_label,
    }


def _print_summary(stats: dict, bin_minutes: float) -> None:
    span_h   = int(stats["span_s"] // 3600)
    span_m   = int((stats["span_s"] % 3600) // 60)
    span_s   = int(stats["span_s"] % 60)
    gap_m    = int(stats["max_gap_s"] // 60)
    gap_s    = int(stats["max_gap_s"] % 60)
    gap_at_h = int(stats["max_gap_at_min"] // 60)
    gap_at_m = int(stats["max_gap_at_min"] % 60)
    tz_name  = stats["t0_local"].strftime("%Z")

    if stats["since_label"]:
        print(f"Filter:       --since '{stats['since_label']}'")
    print(f"Files:        {stats['n_files']:,}")
    print(f"Span:         {span_h}h {span_m:02d}m {span_s:02d}s"
          f"  ({stats['t0_local'].strftime('%Y-%m-%d %H:%M:%S')} {tz_name}"
          f" → {stats['tN_local'].strftime('%H:%M:%S')} {tz_name})")
    print(f"Mean rate:    {stats['mean_rate']:.1f} files/min"
          f"  (per {bin_minutes:.0f}-min bin, non-zero bins only)")
    print(f"Median rate:  {stats['median_rate']:.1f} files/min")
    print(f"Longest gap:  {gap_m}m {gap_s:02d}s"
          f"  (starting at elapsed {gap_at_h}h {gap_at_m:02d}m)")


def _render_cumulative_axis(ax_cum, stats: dict, span_min: float) -> None:
    import matplotlib.ticker as ticker

    ax_cum.step(stats["elapsed_min"], stats["cumulative"],
                where="post", linewidth=1.4, color="steelblue")
    ax_cum.set_ylabel("Cumulative OK fetches")
    ax_cum.set_xlabel("Elapsed (min)")
    ax_cum.set_xlim(0, span_min * 1.01)
    ax_cum.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax_cum.grid(True, alpha=0.25)


def _render_rate_axis(ax_rate, stats: dict, bin_minutes: float, rolling: int, span_min: float) -> None:
    xs = stats["bin_starts"]
    ys = [c / bin_minutes for c in stats["counts"]]

    ax_rate.bar(xs, ys, width=bin_minutes * 0.9, color="steelblue",
                alpha=0.55, label=f"files/{bin_minutes:.0f}min bin")
    ax_rate.plot(xs, stats["rolling_mean"],
                 color="darkorange", linewidth=1.5,
                 label=f"rolling mean ({rolling} bins)")

    refresh_times = [i * _POOL_REFRESH_MIN for i in range(1, int(span_min / _POOL_REFRESH_MIN) + 1)]
    first_marker = True
    for rt in refresh_times:
        ax_rate.axvline(
            rt, color="lightgrey", linestyle="--", linewidth=0.8,
            label="30-min pool-refresh" if first_marker else "_nolegend_",
        )
        first_marker = False

    ax_rate.set_ylabel(f"Files / min  (bin = {bin_minutes:.0f}min)")
    ax_rate.set_xlabel("Elapsed (min)")
    ax_rate.set_xlim(0, span_min * 1.01)
    ax_rate.legend(fontsize=8, loc="upper right")
    ax_rate.grid(True, alpha=0.2)


def _build_output_path(stats: dict) -> Path:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_tag  = stats["t0_local"].strftime("%Y%m%d")
    since_tag = f"_since{stats['since_label'].replace(' ', 'T').replace(':', '')}" if stats["since_label"] else ""
    return _REPORT_DIR / f"raw_write_times_{date_tag}{since_tag}.png"


def _plot(stats: dict, bin_minutes: float, rolling: int) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    span_min = stats["span_s"] / 60.0

    fig, (ax_cum, ax_rate) = plt.subplots(
        2, 1, figsize=(14, 8), sharex=False,
        gridspec_kw={"height_ratios": [1, 1.4]},
    )
    fig.subplots_adjust(hspace=0.35)

    tz_name  = stats["t0_local"].strftime("%Z")
    date_str = stats["t0_local"].strftime("%Y-%m-%d")
    window_str = (
        f"filtered window: since {stats['since_label']} local  •  "
        if stats["since_label"] else ""
    )
    fig.suptitle(
        f"CoinDesk proxy-riding throughput reconstruction  [{window_str}{stats['n_files']:,} files]\n"
        f"{stats['t0_local'].strftime('%Y-%m-%d %H:%M')}–{stats['tN_local'].strftime('%H:%M')} {tz_name}"
        f"  •  {int(stats['span_s']//3600)}h {int((stats['span_s']%3600)//60):02d}m span",
        fontsize=10,
    )

    _render_cumulative_axis(ax_cum, stats, span_min)
    _render_rate_axis(ax_rate, stats, bin_minutes, rolling, span_min)

    out = _build_output_path(stats)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out


if __name__ == "__main__":
    main()
