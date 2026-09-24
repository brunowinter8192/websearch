#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import os
import sys
import time
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p1_log_janitor import maybe_prune_jsonl, maybe_prune_sidecars


# ORCHESTRATOR

def prune_test_workflow() -> None:
    print("=== log_janitor prune test ===")
    os.environ["SEARXNG_LOG_RETENTION_DAYS"] = "14"
    with tempfile.TemporaryDirectory() as tmp:
        failures = run_tests(Path(tmp))
    print()
    if failures:
        print(f"RESULT: {failures} assertion(s) FAILED")
        sys.exit(1)
    print("RESULT: all assertions PASSED")


# FUNCTIONS

def run_tests(tmp_dir: Path) -> int:
    jsonl_path = tmp_dir / "query_log.jsonl"
    sidecar_dir = tmp_dir / "scrape_content"
    failures = 0

    _make_jsonl(jsonl_path)
    _make_sidecars(sidecar_dir)

    print("\n-- Scenario 1: slow-path fires (no marker) --")
    maybe_prune_jsonl(jsonl_path)
    maybe_prune_sidecars(sidecar_dir)

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    failures += _check("JSONL: 3 recent lines kept", len(lines) == 3)
    queries = [json.loads(l)["query"] for l in lines]
    failures += _check("JSONL: no old entries remain", not any("old" in q for q in queries))

    remaining_md = sorted(sidecar_dir.glob("*.md"))
    failures += _check("Sidecar: 1 file remains", len(remaining_md) == 1)
    failures += _check("Sidecar: recent.md kept", remaining_md[0].name == "recent.md")

    jsonl_marker = Path(str(jsonl_path) + ".lastprune")
    sidecar_marker = sidecar_dir / ".lastprune"
    failures += _check("JSONL marker created", jsonl_marker.exists())
    failures += _check("Sidecar marker created", sidecar_marker.exists())

    print("\n-- Scenario 2: fast-path skip (marker recent) --")
    with open(jsonl_path, "a", encoding="utf-8") as f:
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        f.write(json.dumps({"ts": old_ts, "query": "injected-old"}) + "\n")
    maybe_prune_jsonl(jsonl_path)
    lines2 = jsonl_path.read_text(encoding="utf-8").splitlines()
    failures += _check("Fast-path: injected old line NOT pruned (marker recent)", len(lines2) == 4)

    print("\n-- Scenario 3: stale marker → slow-path re-fires --")
    stale = time.time() - 3700
    os.utime(jsonl_marker, (stale, stale))
    maybe_prune_jsonl(jsonl_path)
    lines3 = jsonl_path.read_text(encoding="utf-8").splitlines()
    failures += _check("Stale marker: injected old line pruned (slow-path re-fired)", len(lines3) == 3)

    return failures


def _make_jsonl(path: Path) -> None:
    now = datetime.now(timezone.utc)
    entries = [
        {"ts": (now - timedelta(days=20)).isoformat(), "query": "old-1"},
        {"ts": (now - timedelta(days=20)).isoformat(), "query": "old-2"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-1"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-2"},
        {"ts": (now - timedelta(days=2)).isoformat(), "query": "recent-3"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _make_sidecars(sidecar_dir: Path) -> None:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    old_mtime = time.time() - 20 * 86400
    for name in ("old-a.md", "old-b.md"):
        f = sidecar_dir / name
        f.write_text(f"<!-- {name} -->", encoding="utf-8")
        os.utime(f, (old_mtime, old_mtime))
    (sidecar_dir / "recent.md").write_text("<!-- recent -->", encoding="utf-8")


def _check(label: str, condition: bool) -> int:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    return 0 if condition else 1


if __name__ == "__main__":
    prune_test_workflow()
