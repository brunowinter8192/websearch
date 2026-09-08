# INFRASTRUCTURE

import statistics
from datetime import datetime, timezone

# From state.py: shared riding state shape + constants
from src.news.engine.proxy_riding.state import RiderState, FAIL_THRESHOLD

_BACKFILL_TOTAL = 61_000


# FUNCTIONS

# Derive all metrics from RiderState and job start time.
def _compute_stats(state: RiderState, t_job_start: datetime) -> dict:
    jobs  = state.job_records
    rides = state.ride_records

    fetch_counts = _compute_fetch_counts(jobs, state, t_job_start)

    ride_lengths   = [r.n_urls_attempted for r in rides]
    ride_ok_counts = [r.n_ok             for r in rides]
    ride_len_stats = _distribution_stats(ride_lengths)
    n_proxies_burned     = len(rides)
    proxies_for_backfill = round(n_proxies_burned / max(fetch_counts["n_ok"], 1) * _BACKFILL_TOTAL)
    n_fail_rotations     = sum(1 for r in rides if r.n_failed >= FAIL_THRESHOLD)

    n_urls_with_regwall, retried_ok, retried_failed = _compute_retry_outcome(jobs)
    wasted_ratio = fetch_counts["n_regwall_fetches"] / max(fetch_counts["n_total_fetches"], 1)

    pool_total, pool_windows = _compute_pool_windows(state)
    page_timeout_s = state.page_timeout_ms / 1000
    load_times, load_perc = _compute_load_percentiles(jobs)
    cf_times, cf_perc, cf_subtype_counts = _compute_connect_fail_stats(state)

    return {
        **fetch_counts,
        "ride_ok_counts": ride_ok_counts,
        "ride_len_stats": ride_len_stats,
        "n_proxies_burned": n_proxies_burned,
        "proxies_for_backfill": proxies_for_backfill,
        "n_fail_rotations": n_fail_rotations,
        "retried_ok": retried_ok, "retried_failed": retried_failed,
        "n_urls_with_regwall": n_urls_with_regwall,
        "wasted_ratio": wasted_ratio,
        "termination": state.termination,
        "pool_total": pool_total, "pool_windows": pool_windows,
        "page_timeout_s": page_timeout_s,
        "load_times": load_times,
        "load_perc": load_perc,
        "cf_times": cf_times,
        "cf_perc": cf_perc,
        "cf_subtype_counts": cf_subtype_counts,
    }


# Fetch-level counts, elapsed-time stats, and completion times derived directly from job_records.
def _compute_fetch_counts(jobs: list, state: RiderState, t_job_start: datetime) -> dict:
    n_total_fetches   = len(jobs)
    n_ok              = sum(1 for j in jobs if j.status == "ok")
    n_regwall_fetches = sum(1 for j in jobs if j.status == "regwall")
    n_failed          = sum(1 for j in jobs if j.status in ("failed", "empty"))
    n_connect_fail    = state.n_connect_fail

    elapsed_values = [j.elapsed_s for j in jobs if j.elapsed_s is not None]
    mean_s   = statistics.mean(elapsed_values)   if elapsed_values else None
    median_s = statistics.median(elapsed_values) if elapsed_values else None

    wall_s       = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    urls_per_min = (n_ok / wall_s * 60) if wall_s > 0 and n_ok else None

    ok_completion_s = sorted(
        (j.t_start - t_job_start).total_seconds() + (j.elapsed_s or 0)
        for j in jobs if j.status == "ok" and j.elapsed_s is not None
    )

    return {
        "n_total_fetches": n_total_fetches, "n_ok": n_ok,
        "n_regwall_fetches": n_regwall_fetches, "n_failed": n_failed,
        "n_connect_fail": n_connect_fail,
        "mean_s": mean_s, "median_s": median_s,
        "wall_s": wall_s, "urls_per_min": urls_per_min,
        "ok_completion_s": ok_completion_s,
    }


# Retry outcome: among URLs that saw ≥1 regwall, final status (eventually ok vs stayed failed).
def _compute_retry_outcome(jobs: list) -> tuple[int, int, int]:
    url_final: dict[str, str] = {}
    url_rw:    set[str]       = set()
    for j in jobs:
        url_final[j.url] = j.status
        if j.status == "regwall":
            url_rw.add(j.url)
    retried_ok     = sum(1 for u in url_rw if url_final[u] == "ok")
    retried_failed = len(url_rw) - retried_ok
    return len(url_rw), retried_ok, retried_failed


# Eligible pool over time — bucket pool_samples into 10-min windows.
def _compute_pool_windows(state: RiderState) -> tuple[int, list[dict]]:
    pool_total   = len(state.proxy_pool)
    pool_windows: list[dict] = []
    if state.pool_samples:
        _WIN_S = 600
        max_win = int(state.pool_samples[-1][0] / _WIN_S)
        for k in range(max_win + 1):
            win = [(e, ne, nc) for e, ne, nc in state.pool_samples if int(e / _WIN_S) == k]
            if win:
                min_eligible  = min(ne for _, ne, _ in win)
                avg_eligible  = round(sum(ne for _, ne, _ in win) / len(win))
                peak_cooldown = max(nc for _, _, nc in win)
                pool_windows.append({
                    "window_min":    k * 10,
                    "min_eligible":  min_eligible,
                    "avg_eligible":  avg_eligible,
                    "peak_cooldown": peak_cooldown,
                })
    return pool_total, pool_windows


# OK-fetch load-time inclusive percentiles; None when fewer than 2 samples.
def _compute_load_percentiles(jobs: list) -> tuple[list[float], dict | None]:
    load_times = [j.load_s for j in jobs if j.status == "ok" and j.load_s is not None]
    if len(load_times) < 2:
        return load_times, None
    qs = statistics.quantiles(load_times, n=100, method="inclusive")
    return load_times, {
        "p50": round(qs[49], 3), "p90": round(qs[89], 3), "p95": round(qs[94], 3),
        "p99": round(qs[98], 3), "max": round(max(load_times), 3), "n": len(load_times),
    }


# Connect-fail elapsed-time inclusive percentiles + subtype counts.
def _compute_connect_fail_stats(state: RiderState) -> tuple[list[float], dict | None, dict[str, int]]:
    cf_times    = [r[0] for r in state.connect_fail_records]
    cf_subtypes = [r[1] for r in state.connect_fail_records]
    cf_perc: dict | None = None
    if len(cf_times) >= 2:
        qs = statistics.quantiles(cf_times, n=100, method="inclusive")
        cf_perc = {
            "p50": round(qs[49], 3), "p90": round(qs[89], 3), "p95": round(qs[94], 3),
            "p99": round(qs[98], 3), "max": round(max(cf_times), 3), "n": len(cf_times),
        }
    cf_subtype_counts: dict[str, int] = {}
    for st in cf_subtypes:
        cf_subtype_counts[st] = cf_subtype_counts.get(st, 0) + 1
    return cf_times, cf_perc, cf_subtype_counts


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
