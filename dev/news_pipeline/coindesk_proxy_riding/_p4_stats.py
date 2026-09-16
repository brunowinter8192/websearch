# INFRASTRUCTURE

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p2_browser_rider import RiderState, FAIL_THRESHOLD

_BACKFILL_TOTAL = 61_000


# FUNCTIONS
def _compute_counts(jobs: list, state: RiderState) -> dict:
    n_total_fetches   = len(jobs)
    n_ok              = sum(1 for j in jobs if j.status == "ok")
    n_regwall_fetches = sum(1 for j in jobs if j.status == "regwall")
    n_failed          = sum(1 for j in jobs if j.status in ("failed", "empty"))
    # connect_fail breaks before job_records.append() → use authoritative state counter
    n_connect_fail    = state.n_connect_fail
    return {
        "n_total_fetches": n_total_fetches, "n_ok": n_ok,
        "n_regwall_fetches": n_regwall_fetches, "n_failed": n_failed,
        "n_connect_fail": n_connect_fail,
    }


def _compute_throughput(jobs: list, n_ok: int, t_job_start: datetime) -> dict:
    elapsed_values = [j.elapsed_s for j in jobs if j.elapsed_s is not None]
    mean_s   = statistics.mean(elapsed_values)   if elapsed_values else None
    median_s = statistics.median(elapsed_values) if elapsed_values else None

    wall_s       = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    urls_per_min = (n_ok / wall_s * 60)                    if wall_s > 0 and n_ok else None
    backfill_h   = (_BACKFILL_TOTAL / urls_per_min / 60)   if urls_per_min         else None

    return {
        "mean_s": mean_s, "median_s": median_s, "wall_s": wall_s,
        "urls_per_min": urls_per_min, "backfill_h": backfill_h,
    }


def _compute_size_distributions(jobs: list) -> dict:
    ok_html_sizes = sorted(
        j.char_count for j in jobs if j.status == "ok" and j.char_count is not None
    )
    html_pct = _percentiles(ok_html_sizes)

    ok_md_lens = sorted(
        j.markdown_len for j in jobs
        if j.status == "ok" and getattr(j, "markdown_len", None) is not None
    )
    md_pct = _percentiles(ok_md_lens)

    return {"html_pct": html_pct, "md_pct": md_pct}


def _compute_completion_times(jobs: list, t_job_start: datetime) -> list:
    return sorted(
        (j.t_start - t_job_start).total_seconds() + (j.elapsed_s or 0)
        for j in jobs if j.status == "ok" and j.elapsed_s is not None
    )


def _compute_ride_stats(rides: list, n_ok: int) -> dict:
    ride_lengths   = [r.n_urls_attempted for r in rides]
    ride_ok_counts = [r.n_ok             for r in rides]
    ride_len_stats = _distribution_stats(ride_lengths)

    n_proxies_burned     = len(rides)
    proxies_for_backfill = round(n_proxies_burned / max(n_ok, 1) * _BACKFILL_TOTAL)
    n_fail_rotations     = sum(1 for r in rides if r.n_failed >= FAIL_THRESHOLD)

    return {
        "ride_lengths": ride_lengths, "ride_ok_counts": ride_ok_counts,
        "ride_len_stats": ride_len_stats,
        "n_proxies_burned": n_proxies_burned,
        "proxies_for_backfill": proxies_for_backfill,
        "n_fail_rotations": n_fail_rotations,
    }


# Regwall rate by ride position (position = URL index within a proxy ride)
def _compute_regwall_by_position(jobs: list) -> dict:
    rw_by_pos:    dict[int, int] = {}
    total_by_pos: dict[int, int] = {}
    for j in jobs:
        pos = j.ride_position
        total_by_pos[pos] = total_by_pos.get(pos, 0) + 1
        if j.status == "regwall":
            rw_by_pos[pos] = rw_by_pos.get(pos, 0) + 1
    max_pos = max(total_by_pos.keys()) if total_by_pos else 0
    return {
        pos: rw_by_pos.get(pos, 0) / total_by_pos[pos]
        for pos in range(1, max_pos + 1)
        if total_by_pos.get(pos, 0) > 0
    }


# Retry outcome: among URLs that saw at least one regwall, final status
def _compute_retry_outcomes(jobs: list) -> dict:
    url_final: dict[str, str] = {}
    url_rw:    set[str]       = set()
    for j in jobs:
        url_final[j.url] = j.status
        if j.status == "regwall":
            url_rw.add(j.url)
    retried_ok     = sum(1 for u in url_rw if url_final[u] == "ok")
    retried_failed = len(url_rw) - retried_ok
    return {
        "retried_ok": retried_ok, "retried_failed": retried_failed,
        "n_urls_with_regwall": len(url_rw),
    }


# Derive all metrics from RiderState and job start time.
def _compute_stats(state: RiderState, t_job_start: datetime) -> dict:
    jobs  = state.job_records
    rides = state.ride_records

    counts     = _compute_counts(jobs, state)
    throughput = _compute_throughput(jobs, counts["n_ok"], t_job_start)
    sizes      = _compute_size_distributions(jobs)
    ok_completion_s     = _compute_completion_times(jobs, t_job_start)
    ride_stats          = _compute_ride_stats(rides, counts["n_ok"])
    regwall_rate_by_pos = _compute_regwall_by_position(jobs)
    retry               = _compute_retry_outcomes(jobs)

    wasted_ratio = counts["n_regwall_fetches"] / max(counts["n_total_fetches"], 1)

    return {
        **counts,
        **throughput,
        **sizes,
        "ok_completion_s": ok_completion_s,
        **ride_stats,
        "regwall_rate_by_pos": regwall_rate_by_pos,
        **retry,
        "wasted_ratio": wasted_ratio,
        "termination": state.termination,
    }


# Compute p10/p25/p50/p75/p90/p95 from a sorted list; return None if empty.
def _percentiles(sorted_values: list) -> dict | None:
    n = len(sorted_values)
    if n == 0:
        return None
    if n == 1:
        return {k: sorted_values[0] for k in ("p10", "p25", "p50", "p75", "p90", "p95")}
    qs = statistics.quantiles(sorted_values, n=100, method="inclusive")
    return {
        "p10": int(round(qs[9])),  "p25": int(round(qs[24])), "p50": int(round(qs[49])),
        "p75": int(round(qs[74])), "p90": int(round(qs[89])), "p95": int(round(qs[94])),
    }


# Compute mean/median/min/max of a list; return None-filled dict if empty.
def _distribution_stats(values: list) -> dict:
    if not values:
        return {"mean": None, "median": None, "min": None, "max": None}
    return {
        "mean":   round(statistics.mean(values),   2),
        "median": round(statistics.median(values), 2),
        "min":    min(values),
        "max":    max(values),
    }
