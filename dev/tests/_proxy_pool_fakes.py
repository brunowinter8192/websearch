# INFRASTRUCTURE
from pathlib import Path


# FUNCTIONS

def _attempt(proxy: str, url: str, ts: str, result: str = "ok") -> dict:
    return {"proxy_key": proxy, "url": url, "ts": ts, "result": result}


def _refresh(size: int, ts: str) -> dict:
    return {"event": "pool_refresh", "size": size, "ts": ts}


def _write_and_read_md(compute_stats, write_md, tmp_path: Path, events: list[dict],
                       target: int = 10, done: int = 5) -> str:
    stats = compute_stats(events)
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    write_md(job_dir, "test-job", target, done, stats)
    return (job_dir / "job.md").read_text(encoding="utf-8")
