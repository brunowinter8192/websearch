# INFRASTRUCTURE

import json
import shutil
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import PROXY_TS_FMT


# FUNCTIONS

class Janitor:
    def __init__(self, jobs_dir: Path, log_dir: Path, report_dir: Path):
        self._jobs_dir   = jobs_dir
        self._log_dir    = log_dir
        self._report_dir = report_dir

    def start_job(self, job_id: str) -> None:
        _wipe_dir(self._log_dir)
        _wipe_dir(self._report_dir)
        print(f"[janitor] start_job {job_id!r}: transient logs wiped")

    def end_job(
        self,
        job_id: str,
        jsonl_path: Path,
        target_count: int,
        done_count: int,
    ) -> None:
        job_dir = self._jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        events = _read_events(jsonl_path)
        stats  = _compute_stats(events)

        _write_plot(job_dir, stats)
        _write_md(job_dir, job_id, target_count, done_count, stats)

        jsonl_path.unlink()
        _wipe_dir(self._log_dir)
        _wipe_dir(self._report_dir)
        print(f"[janitor] end_job {job_id!r}: job.md + plot → {job_dir}  transient dirs wiped")


def _wipe_dir(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def _read_events(jsonl_path: Path) -> list[dict]:
    events = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _compute_stats(events: list[dict]) -> dict:
    all_ts = [_parse_ts(e["ts"]) for e in events if "ts" in e]
    if not all_ts:
        return {
            "t0": None, "total_s": 0.0, "mean_ih": None,
            "median_ih": None, "pool_sizes": [], "ok_ts": [], "windows": [],
            "source_batches": [],
        }

    t0      = min(all_ts)
    total_s = (max(all_ts) - t0).total_seconds()

    ok_ts = sorted(
        _parse_ts(e["ts"]) for e in events if e.get("result") == "ok"
    )
    deltas    = [(ok_ts[i + 1] - ok_ts[i]).total_seconds() for i in range(len(ok_ts) - 1)]
    mean_ih   = statistics.mean(deltas)   if deltas else None
    median_ih = statistics.median(deltas) if deltas else None

    pool_sizes     = [e["size"] for e in events if e.get("event") == "pool_refresh"]
    windows        = _compute_window_stats(events, t0)
    source_batches = _group_pool_sources(events)

    return {
        "t0":            t0,
        "total_s":       total_s,
        "mean_ih":       mean_ih,
        "median_ih":     median_ih,
        "pool_sizes":    pool_sizes,
        "ok_ts":         ok_ts,
        "windows":       windows,
        "source_batches": source_batches,
    }


def _parse_ts(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, PROXY_TS_FMT).replace(tzinfo=timezone.utc)


def _compute_window_stats(events: list[dict], t0: datetime) -> list[dict]:
    attempt_events = [e for e in events if "proxy_key" in e]
    refresh_events = [e for e in events if e.get("event") == "pool_refresh"]

    if not attempt_events:
        return []

    max_ts     = max(_parse_ts(e["ts"]) for e in attempt_events)
    max_window = int((max_ts - t0).total_seconds() / 3600)

    refresh_by_win = [
        (int((_parse_ts(e["ts"]) - t0).total_seconds() / 3600), e["size"])
        for e in refresh_events
    ]

    return [_compute_one_window(k, attempt_events, t0, refresh_by_win) for k in range(max_window + 1)]


def _compute_one_window(
    k: int, attempt_events: list[dict], t0: datetime, refresh_by_win: list[tuple[int, int]],
) -> dict:
    win_events = [
        e for e in attempt_events
        if int((_parse_ts(e["ts"]) - t0).total_seconds() / 3600) == k
    ]

    probiert       = len({e["proxy_key"] for e in win_events})
    erfolgreich    = len({e["proxy_key"] for e in win_events if e.get("result") == "ok"})
    urls_handled   = len({e["url"] for e in win_events})
    fetch_attempts = len(win_events)

    prior = [(wi, sz) for wi, sz in refresh_by_win if wi <= k]
    pool_size = prior[-1][1] if prior else None

    return {
        "window":         k,
        "probiert":       probiert,
        "erfolgreich":    erfolgreich,
        "urls_handled":   urls_handled,
        "fetch_attempts": fetch_attempts,
        "pool_size":      pool_size,
    }


def _group_pool_sources(events: list[dict]) -> list[list[dict]]:
    batches: list[list[dict]] = []
    current: list[dict] | None = None
    for e in events:
        if e.get("event") == "pool_refresh":
            if current is not None:
                batches.append(current)
            current = []
        elif e.get("event") == "pool_source":
            if current is not None:
                current.append(e)
    if current is not None:
        batches.append(current)
    return batches


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
    job_dir: Path,
    job_id: str,
    target_count: int,
    done_count: int,
    stats: dict,
) -> None:
    def fmt_s(v: "float | None") -> str:
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
    lines += _md_window_table(stats)
    lines += _md_source_breakdown(stats)

    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")


def _md_window_table(stats: dict) -> list[str]:
    if not stats["windows"]:
        return []
    lines = [
        "## Proxy usage per 60-min window",
        "",
        "| Window | Probiert | Erfolgreich | URLs handled | Fetch-Versuche | Pool size |",
        "|---|---|---|---|---|---|",
    ]
    for w in stats["windows"]:
        ps = str(w["pool_size"]) if w["pool_size"] is not None else "—"
        lines.append(
            f"| {w['window']} | {w['probiert']} | {w['erfolgreich']}"
            f" | {w['urls_handled']} | {w['fetch_attempts']} | {ps} |"
        )
    lines.append("")
    return lines


def _md_source_breakdown(stats: dict) -> list[str]:
    non_empty = [b for b in stats["source_batches"] if b]
    if not non_empty:
        return []
    lines = [
        "## Pool source breakdown",
        "",
        "Per-source raw proxy counts are before cross-repo dedup. "
        "Sum of counts exceeds Pool size — overlap between repos is deduped in `load_backfill_pool()`.",
        "",
    ]
    for i, batch in enumerate(non_empty):
        label = "Refresh 0 (startup)" if i == 0 else f"Refresh {i}"
        lines += [
            f"### {label}",
            "",
            "| URL | Result | Count |",
            "|---|---|---|",
        ]
        for src in batch:
            result = "ok" if src["ok"] else "fail"
            lines.append(f"| {src['url']} | {result} | {src['count']} |")
        lines.append("")
    return lines
