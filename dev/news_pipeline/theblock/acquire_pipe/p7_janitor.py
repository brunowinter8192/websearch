# INFRASTRUCTURE

import json
import shutil
import statistics
from datetime import datetime, timezone
from pathlib import Path

ACQUIRE_BASE = Path(__file__).parent
LOG_DIR      = ACQUIRE_BASE / "acquire_pipe_logs"
REPORT_DIR   = ACQUIRE_BASE / "acquire_pipe_reports"
JOBS_DIR     = ACQUIRE_BASE / "acquire_pipe_jobs"
_TS_FMT      = "%Y-%m-%dT%H:%M:%SZ"


# FUNCTIONS

def start_job(job_id: str) -> None:
    _wipe_dir(LOG_DIR)
    _wipe_dir(REPORT_DIR)
    print(f"[janitor] start_job {job_id!r}: transient logs wiped")


def _wipe_dir(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def end_job(job_id: str, jsonl_path: Path, target_count: int, done_count: int) -> None:
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    events = _read_events(jsonl_path)
    stats  = _compute_stats(events)

    _write_plot(job_dir, stats)
    _write_md(job_dir, job_id, target_count, done_count, stats)

    jsonl_path.unlink()
    _wipe_dir(LOG_DIR)
    _wipe_dir(REPORT_DIR)
    print(f"[janitor] end_job {job_id!r}: job.md + plot → {job_dir}  transient dirs wiped")


def _read_events(jsonl_path: Path) -> list[dict]:
    events = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _parse_ts(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, _TS_FMT).replace(tzinfo=timezone.utc)


def _compute_stats(events: list[dict]) -> dict:
    all_ts = [_parse_ts(e["ts"]) for e in events if "ts" in e]
    if not all_ts:
        return {
            "t0": None, "total_s": 0.0, "mean_ih": None,
            "median_ih": None, "pool_sizes": [], "ok_ts": [],
        }

    t0      = min(all_ts)
    total_s = (max(all_ts) - t0).total_seconds()

    ok_ts = sorted(
        _parse_ts(e["ts"]) for e in events if e.get("result") == "ok"
    )
    deltas    = [(ok_ts[i + 1] - ok_ts[i]).total_seconds() for i in range(len(ok_ts) - 1)]
    mean_ih   = statistics.mean(deltas)   if deltas else None
    median_ih = statistics.median(deltas) if deltas else None

    pool_sizes = [e["size"] for e in events if e.get("event") == "pool_refresh"]

    return {
        "t0":        t0,
        "total_s":   total_s,
        "mean_ih":   mean_ih,
        "median_ih": median_ih,
        "pool_sizes": pool_sizes,
        "ok_ts":     ok_ts,
    }


def _write_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    t0    = stats["t0"]
    ok_ts = stats["ok_ts"]

    if t0 is None or not ok_ts:
        x, y = [0.0], [0]
    else:
        x = [0.0] + [(ts - t0).total_seconds() for ts in ok_ts]
        y = list(range(len(x)))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.step(x, y, where="post", linewidth=1.5)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Cumulative OK fetches")
    ax.set_title("Cumulative hits over time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(job_dir / "cumulative_hits.png", dpi=100)
    plt.close(fig)


def _write_md(
    job_dir: Path, job_id: str,
    target_count: int, done_count: int,
    stats: dict,
) -> None:
    def fmt_s(v: float | None) -> str:
        return f"{v:.1f}s" if v is not None else "—"

    pool_str = ", ".join(str(s) for s in stats["pool_sizes"]) if stats["pool_sizes"] else "—"

    lines = [
        f"# Acquire-pipe job — {job_id}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| URLs | {target_count} target, {done_count} completed |",
        f"| Mean inter-hit | {fmt_s(stats['mean_ih'])} |",
        f"| Median inter-hit | {fmt_s(stats['median_ih'])} |",
        f"| Total time | {fmt_s(stats['total_s'])} |",
        f"| Pool size (per refresh) | {pool_str} |",
        "",
        "![Cumulative hits](cumulative_hits.png)",
        "",
    ]
    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")
