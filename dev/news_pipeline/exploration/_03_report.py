# INFRASTRUCTURE
from datetime import date, datetime, timezone
from pathlib import Path

COINDESK_ORIGIN = date(2013, 9, 1)


# FUNCTIONS

def write_run_report(
    path: Path,
    ts: str,
    run_elapsed: float,
    clicks_done: int,
    total_urls: int,
    oldest_date: str,
    stop_reason: str,
    click_times: list[float],
    stage_a_cap: int | None,
    disabled_retry_hits: int = 0,
) -> None:
    cap_label = str(stage_a_cap) if stage_a_cap is not None else "UNCAPPED"
    elapsed_str = format_elapsed(run_elapsed)

    lines: list[str] = []
    lines += _render_header(ts, cap_label)
    lines += _render_summary(clicks_done, total_urls, oldest_date, stop_reason,
                              disabled_retry_hits, elapsed_str, run_elapsed)

    if not click_times:
        lines.append("_(No click timing data — 0 clicks completed)_")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    stats = compute_timing_stats(click_times)
    lines += _render_timing_table(stats)
    lines += _render_growth_assessment(stats)
    lines += _render_stage_b_projection(oldest_date, clicks_done, run_elapsed, elapsed_str, stats["avg_t"])

    path.write_text("\n".join(lines), encoding="utf-8")


def format_elapsed(run_elapsed: float) -> str:
    h, rem = divmod(int(run_elapsed), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


def _render_header(ts: str, cap_label: str) -> list:
    lines: list[str] = []
    lines.append("# CoinDesk Backfill — Stage A Sanity Report")
    lines.append(f"\n**Run:** {ts}  |  **Cap:** {cap_label}\n")
    return lines


def _render_summary(clicks_done: int, total_urls: int, oldest_date: str, stop_reason: str,
                     disabled_retry_hits: int, elapsed_str: str, run_elapsed: float) -> list:
    lines = ["## Summary\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Clicks done | {clicks_done} |")
    lines.append(f"| Distinct URLs collected | {total_urls} |")
    lines.append(f"| Oldest date reached | {oldest_date} |")
    lines.append(f"| Stop reason | {stop_reason} |")
    lines.append(f"| Disabled-retry recoveries | {disabled_retry_hits} |")
    lines.append(f"| Total wall-clock time | {elapsed_str} ({run_elapsed:.0f}s) |\n")
    return lines


def compute_timing_stats(click_times: list) -> dict:
    avg_t = sum(click_times) / len(click_times)
    min_t = min(click_times)
    max_t = max(click_times)
    n10 = min(10, len(click_times))
    first10_avg = sum(click_times[:n10]) / n10
    last10_avg = sum(click_times[-n10:]) / n10
    trend = last10_avg - first10_avg
    return {
        "avg_t": avg_t, "min_t": min_t, "max_t": max_t,
        "first10_avg": first10_avg, "last10_avg": last10_avg, "trend": trend,
    }


def _render_timing_table(stats: dict) -> list:
    lines = ["## Per-Click Timing\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Average | {stats['avg_t']:.2f}s |")
    lines.append(f"| Min | {stats['min_t']:.2f}s |")
    lines.append(f"| Max | {stats['max_t']:.2f}s |")
    lines.append(f"| First-10 avg | {stats['first10_avg']:.2f}s |")
    lines.append(f"| Last-10 avg | {stats['last10_avg']:.2f}s |")
    trend = stats["trend"]
    trend_label = f"+{trend:.2f}s (slowdown)" if trend > 0.3 else f"{trend:+.2f}s (stable)"
    lines.append(f"| Trend (last10 − first10) | {trend_label} |\n")
    return lines


def _render_growth_assessment(stats: dict) -> list:
    trend = stats["trend"]
    lines = ["## DOM Growth Assessment\n"]
    if trend > 0.5:
        lines.append(f"**Significant slowdown detected: +{trend:.2f}s first→last.**")
        lines.append("At this trajectory Stage B will stall badly at high depth.")
        lines.append("Recommendation: drop `timeLabel` DOM walk from `_JS_EXTRACT` and switch to delta extraction.")
    elif trend > 0.3:
        lines.append(f"**Moderate slowdown: +{trend:.2f}s.** Monitor early in Stage B; delta extraction may be needed above ~1 000 clicks.")
    else:
        lines.append(f"Per-click time is stable ({trend:+.2f}s first→last trend). Full DOM re-scan acceptable for Stage B.\n")
    return lines


def _render_stage_b_projection(oldest_date: str, clicks_done: int, run_elapsed: float,
                                elapsed_str: str, avg_t: float) -> list:
    lines = ["\n## Stage B Projection\n"]
    if oldest_date != "(none)" and clicks_done > 0:
        try:
            today = datetime.now(timezone.utc).date()
            oldest_dt = datetime.strptime(oldest_date, "%Y-%m-%d").date()
            days_covered = max(1, (today - oldest_dt).days)
            days_remaining = max(0, (oldest_dt - COINDESK_ORIGIN).days)
            rate = days_covered / clicks_done
            extra_clicks = int(days_remaining / rate) if rate > 0 else 0
            extra_secs = avg_t * extra_clicks
            total_clicks = clicks_done + extra_clicks
            total_secs = run_elapsed + extra_secs
            h2, r2 = divmod(int(total_secs), 3600)
            m2, _ = divmod(r2, 60)
            total_time_str = f"{h2}h {m2}m" if h2 else f"{m2}m"
            lines.append(f"- Stage A: **{clicks_done} clicks** → **{days_covered} days** back to `{oldest_date}` in {elapsed_str}")
            lines.append(f"- Rate: **{rate:.1f} days of history per click** at {avg_t:.1f}s/click")
            lines.append(f"- Remaining to CoinDesk founding ({COINDESK_ORIGIN}): **~{days_remaining} days**")
            lines.append(f"- Estimated additional clicks: **~{extra_clicks:,}**")
            lines.append(f"- Estimated additional time at current pace: **~{extra_secs / 3600:.1f}h**")
            lines.append(f"- **Total full-run estimate: ~{total_clicks:,} clicks / ~{total_time_str}**")
            lines.append(f"\n*(Linear projection — actual floor unknown; feed may end before founding date.)*")
        except Exception as e:
            lines.append(f"_(Projection error: {e})_")
    else:
        lines.append("_(Insufficient data for projection)_")
    return lines
