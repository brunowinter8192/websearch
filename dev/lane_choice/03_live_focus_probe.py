#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORKTREE_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = WORKTREE_ROOT / "cli.py"
PYTHON = WORKTREE_ROOT / "venv" / "bin" / "python"
REPORT_DIR = SCRIPT_DIR / "md"

LANE = "chromium"
SUBCOMMAND = "scrape_url_chromium"
POLL_INTERVAL_S = 0.25
COUNTDOWN_S = 10
DEFAULT_URL = "https://example.com"


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Live HUMAN focus-steal probe: launches one or more real scrapes via THIS worktree's "
            "own cli.py (never the `websearch` PATH wrapper), after a single countdown, one fresh "
            "browser per URL back-to-back, while polling a macOS frontmost-app instrument "
            "continuously across the whole sequence. Watch your own focus/typing during the run, "
            "then read the printed verdict."
        )
    )
    parser.add_argument(
        "--url", action="append", dest="urls",
        help=f"URL to scrape — repeat for multiple URLs, each run back-to-back with a fresh browser "
        f"after one shared countdown (default if omitted: {DEFAULT_URL})",
    )
    args = parser.parse_args()
    urls = args.urls or [DEFAULT_URL]
    live_focus_probe_workflow(urls)


# FUNCTIONS

def live_focus_probe_workflow(urls: list[str]) -> None:
    print_countdown(LANE)
    baseline_app = get_frontmost_app()
    print(f"Baseline frontmost app (post-countdown, expected throughout): {baseline_app}\n")

    frontmost_samples: list[tuple[float, str]] = []
    stop_event = threading.Event()
    t0 = time.perf_counter()
    frontmost_thread = threading.Thread(
        target=poll_frontmost_loop, args=(t0, frontmost_samples, stop_event)
    )
    frontmost_thread.start()

    url_runs = run_urls_in_sequence(urls, SUBCOMMAND, t0)

    stop_event.set()
    frontmost_thread.join()

    print_url_runs(url_runs)

    verdict = compute_verdict(baseline_app, frontmost_samples)
    print_verdict(verdict)

    per_url_verdicts = compute_per_url_verdicts(baseline_app, frontmost_samples, url_runs)
    print_per_url_verdicts(per_url_verdicts)

    report_path = write_report(
        LANE, url_runs, baseline_app, frontmost_samples, verdict, per_url_verdicts,
    )
    print(f"\nFull sample series report: {report_path}")


def print_countdown(lane: str) -> None:
    print("=" * 64)
    print(f"LIVE FOCUS-STEAL PROBE — {lane} lane")
    print("=" * 64)
    print(">>> SWITCH TO ANOTHER APPLICATION NOW AND START TYPING. <<<")
    print(f"The browser launches in {COUNTDOWN_S} seconds.\n")
    for remaining in range(COUNTDOWN_S, 0, -1):
        print(f"  launching in {remaining}s...", flush=True)
        time.sleep(1)
    print("  LAUNCHING NOW.\n", flush=True)


def poll_frontmost_loop(t0: float, samples: list[tuple[float, str]], stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        app = get_frontmost_app()
        samples.append((round(time.perf_counter() - t0, 2), app))
        time.sleep(POLL_INTERVAL_S)


def run_urls_in_sequence(urls: list[str], subcommand: str, t0: float) -> list[dict]:
    url_runs = []
    for i, url in enumerate(urls, start=1):
        cmd = [str(PYTHON), str(CLI_PATH), subcommand, url]
        start_s = round(time.perf_counter() - t0, 2)
        print(f"LAUNCHING NOW ({i}/{len(urls)}): {' '.join(cmd)}  (cwd={WORKTREE_ROOT})")
        result = subprocess.run(cmd, cwd=WORKTREE_ROOT, capture_output=True, text=True)
        end_s = round(time.perf_counter() - t0, 2)
        print(f"  exit code: {result.returncode}  (span: t={start_s}s-{end_s}s)")
        if result.returncode != 0:
            print("  stderr (last 20 lines):")
            print("\n".join(f"  {line}" for line in result.stderr.splitlines()[-20:]))
        url_runs.append({
            "url": url, "cmd": cmd, "start_s": start_s, "end_s": end_s,
            "returncode": result.returncode,
        })
    return url_runs


def print_url_runs(url_runs: list[dict]) -> None:
    print(f"\nPer-URL launch spans (elapsed seconds since the countdown ended, {len(url_runs)} URL(s)):")
    for i, run in enumerate(url_runs, start=1):
        print(f"  [{i}] {run['url']}: t={run['start_s']}s-{run['end_s']}s, exit={run['returncode']}")


def print_verdict(verdict: dict) -> None:
    print("\n" + "=" * 64)
    print("VERDICT")
    print("=" * 64)
    print(
        f"Frontmost app: {verdict['fm_total']} samples "
        f"(mean interval {verdict['fm_mean_interval_s']}s, max gap {verdict['fm_max_gap_s']}s, "
        f"~{verdict['fm_effective_rate_hz']} samples/s), {verdict['fm_dev_count']} deviations, "
        f"longest continuous deviation {verdict['fm_longest_s']}s"
    )
    if verdict["fm_dev_offsets"]:
        print(f"  offsets (s since launch): {verdict['fm_dev_offsets']}")
    print(
        f"\nNote: actual sampling cadence is set by each osascript round-trip, not by the nominal "
        f"POLL_INTERVAL_S={POLL_INTERVAL_S}s sleep alone (see mean interval/max gap above) — a "
        "0-deviation line only covers the span actually sampled, not necessarily every moment of "
        "the run."
    )


def compute_per_url_verdicts(
    baseline_app: str, frontmost_samples: list[tuple[float, str]], url_runs: list[dict],
) -> list[tuple[dict, dict]]:
    return [
        (run, compute_verdict(baseline_app, _samples_in_window(frontmost_samples, run["start_s"], run["end_s"])))
        for run in url_runs
    ]


def print_per_url_verdicts(per_url_verdicts: list[tuple[dict, dict]]) -> None:
    print("\n" + "=" * 64)
    print("PER-URL VERDICT (instrument samples sliced to each URL's own launch span)")
    print("=" * 64)
    for run, verdict in per_url_verdicts:
        print(f"\n[{run['url']}]  t={run['start_s']}s-{run['end_s']}s  exit={run['returncode']}")
        print(
            f"  {verdict['fm_total']} samples, {verdict['fm_dev_count']} deviations, "
            f"longest continuous deviation {verdict['fm_longest_s']}s"
        )


def write_report(
    lane: str, url_runs: list[dict], baseline_app: str,
    frontmost_samples: list[tuple[float, str]], verdict: dict, per_url_verdicts: list[tuple[dict, dict]],
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"03_live_focus_probe_report_{ts}.md"

    lines = _format_report_header(ts, lane, url_runs, baseline_app)
    lines += _format_url_spans(url_runs)
    lines += _format_verdict_sections(verdict)
    lines += _format_per_url_verdict_sections(per_url_verdicts)
    lines += _format_sample_series(frontmost_samples)

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def get_frontmost_app() -> str:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def compute_verdict(baseline_app: str, frontmost_samples: list[tuple[float, str]]) -> dict:
    fm_deviations = [(t, app) for t, app in frontmost_samples if app != baseline_app]
    fm_stats = instrument_resolution_stats(frontmost_samples)
    return {
        "fm_total": len(frontmost_samples),
        "fm_dev_count": len(fm_deviations),
        "fm_longest_s": longest_continuous_run(frontmost_samples, lambda app: app != baseline_app),
        "fm_dev_offsets": [t for t, _ in fm_deviations],
        "fm_mean_interval_s": fm_stats["mean_interval_s"],
        "fm_max_gap_s": fm_stats["max_gap_s"],
        "fm_effective_rate_hz": fm_stats["effective_rate_hz"],
    }


def _samples_in_window(samples: list[tuple[float, object]], start_s: float, end_s: float) -> list[tuple[float, object]]:
    return [(t, v) for t, v in samples if start_s <= t <= end_s]


def _format_report_header(ts: str, lane: str, url_runs: list[dict], baseline_app: str) -> list:
    return [
        f"## Live focus-steal probe ({ts})",
        f"- Lane: {lane}",
        f"- URLs ({len(url_runs)}): {', '.join(run['url'] for run in url_runs)}",
        f"- Worktree root: {WORKTREE_ROOT}",
        f"- Countdown given before the first launch (one countdown for the whole sequence): {COUNTDOWN_S}s",
        f"- Baseline (expected) frontmost app: `{baseline_app}`",
        f"- Nominal poll interval (sleep() argument, NOT the real cadence — see resolution below): "
        f"{POLL_INTERVAL_S}s",
        "",
        "## Per-URL launch spans (elapsed seconds since the countdown ended — the instrument polled "
        "continuously across all of them, one fresh browser per URL)",
    ]


def _format_url_spans(url_runs: list[dict]) -> list:
    lines = []
    for i, run in enumerate(url_runs, start=1):
        lines.append(
            f"- [{i}] `{run['url']}`: t={run['start_s']}s-{run['end_s']}s "
            f"(wall {round(run['end_s'] - run['start_s'], 2)}s), exit code {run['returncode']}"
        )
    return lines


def _format_verdict_sections(verdict: dict) -> list:
    lines = [
        "",
        "## Overall verdict (whole sequence, all URLs pooled)",
        f"- {verdict['fm_total']} samples, {verdict['fm_dev_count']} deviations, "
        f"longest continuous deviation {verdict['fm_longest_s']}s",
        "",
        "## Observed sampling resolution (real, not nominal — see sample_gaps/instrument_resolution_stats)",
        f"- Mean interval {verdict['fm_mean_interval_s']}s, max gap {verdict['fm_max_gap_s']}s, "
        f"effective rate ~{verdict['fm_effective_rate_hz']} samples/s",
        "- A 0-deviation line above only covers the span actually sampled at this cadence — a run "
        "shorter than the max gap between two samples is not guaranteed to be caught by the instrument.",
        "",
        f"## Deviation offsets ({verdict['fm_dev_count']} of {verdict['fm_total']})",
    ]
    lines.append("NONE" if not verdict["fm_dev_offsets"] else ", ".join(f"t={t}s" for t in verdict["fm_dev_offsets"]))
    return lines


def _format_per_url_verdict_sections(per_url_verdicts: list[tuple[dict, dict]]) -> list:
    lines = ["", "## Per-URL verdict (instrument samples sliced to each URL's own launch span above)"]
    for run, url_verdict in per_url_verdicts:
        lines += [
            f"### `{run['url']}` — t={run['start_s']}s-{run['end_s']}s, exit code {run['returncode']}",
            f"- {url_verdict['fm_total']} samples, {url_verdict['fm_dev_count']} deviations, "
            f"longest continuous deviation {url_verdict['fm_longest_s']}s",
            "",
        ]
    return lines


def _format_sample_series(frontmost_samples: list[tuple[float, str]]) -> list:
    lines = ["## Full sample series"]
    lines += [f"- t={t}s: {app}" for t, app in frontmost_samples]
    return lines


def instrument_resolution_stats(samples: list[tuple[float, object]]) -> dict:
    n = len(samples)
    if n < 2:
        return {"sample_count": n, "mean_interval_s": None, "max_gap_s": None, "effective_rate_hz": None}
    gaps = sample_gaps(samples)
    span = samples[-1][0] - samples[0][0]
    return {
        "sample_count": n,
        "mean_interval_s": round(span / (n - 1), 3),
        "max_gap_s": round(max(gaps), 3),
        "effective_rate_hz": round((n - 1) / span, 2) if span > 0 else None,
    }


def longest_continuous_run(samples: list[tuple[float, object]], is_deviation) -> float:
    longest = 0.0
    run_start = None
    for t, v in samples:
        if is_deviation(v):
            if run_start is None:
                run_start = t
        else:
            if run_start is not None:
                longest = max(longest, t - run_start)
                run_start = None
    if run_start is not None:
        gaps = sample_gaps(samples)
        mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
        longest = max(longest, samples[-1][0] - run_start + mean_gap)
    return round(longest, 2)


def sample_gaps(samples: list[tuple[float, object]]) -> list[float]:
    return [samples[i + 1][0] - samples[i][0] for i in range(len(samples) - 1)]


if __name__ == "__main__":
    main()
