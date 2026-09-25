#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
PROJECT_ROOT = PIPELINE_DIR.parent.parent
LOG_DIR = PROJECT_ROOT / "src" / "logs"
LAST_RUN_FILE = LOG_DIR / "coindesk_pipeline_last_run.txt"
PYTHON = str(PROJECT_ROOT / "venv" / "bin" / "python")

PRECONDITION_URL = "https://www.coindesk.com"
PRECONDITION_TIMEOUT = 10


# ORCHESTRATOR

def main():
    pipeline_workflow()


# FUNCTIONS

def pipeline_workflow():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = setup_logging()
    log.info("=== CoinDesk pipeline started ===")

    if not check_preconditions(log):
        log.error("Precondition check failed — aborting.")
        sys.exit(1)

    clear_intermediates(log)

    discover_json = run_stage_discover(log)
    if discover_json is None:
        log.error("Stage 01 failed — aborting.")
        sys.exit(1)

    filtered_json, n_total, n_skipped, n_new = run_stage_dedup(log, discover_json)
    if filtered_json is None:
        log.error("Stage 04 failed — aborting.")
        sys.exit(1)
    log.info(f"STAGE 04: dedup → {n_total} total, {n_skipped} already indexed, {n_new} new")

    if n_new == 0:
        log.info("Nothing new to scrape — pipeline complete.")
        write_last_run_marker(log)
        return

    n_ok, n_failed = run_stage_scrape(log, filtered_json)
    log.info(f"STAGE 02b: scrape → {n_ok} ok, {n_failed} failed")

    if n_ok == 0:
        log.warning("Stage 02b produced 0 successful scrapes — skipping cleanup + publish.")
        write_last_run_marker(log)
        return

    n_cleaned = run_stage_cleanup(log)
    log.info(f"STAGE 03: cleanup → {n_cleaned} files cleaned")

    n_copied, n_chunks = run_stage_publish(log)
    log.info(f"STAGE 05: publish → {n_copied} copied, {n_chunks} chunks indexed")

    log.info("=== Pipeline complete ===")
    write_last_run_marker(log)


def setup_logging() -> logging.Logger:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = LOG_DIR / f"coindesk_pipeline_{today}.log"
    fmt = "[%(asctime)s] %(levelname)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger("coindesk_pipeline")
    log.info(f"Log file: {log_file}")
    return log


def check_preconditions(log: logging.Logger) -> bool:
    log.info("Checking preconditions …")

    try:
        with urllib.request.urlopen(PRECONDITION_URL, timeout=PRECONDITION_TIMEOUT):
            log.info("  [OK] Internet reachable (coindesk.com)")
    except Exception as e:
        log.error(f"  [FAIL] Internet unreachable: {e}")
        return False

    result = subprocess.run(
        ["rag-cli", "list_collections"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error(f"  [FAIL] rag-cli not callable: {result.stderr.strip()}")
        return False
    log.info("  [OK] rag-cli callable")

    return True


def clear_intermediates(log: logging.Logger):
    dirs_to_clear = [
        PIPELINE_DIR / "02b_data",
        PIPELINE_DIR / "03_data",
    ]
    for d in dirs_to_clear:
        if d.exists():
            for f in d.glob("*.md"):
                f.unlink()
            manifest = d / "manifest.json"
            if manifest.exists():
                manifest.unlink()
            log.info(f"Cleared intermediate: {d.name}/")


def run_stage_discover(log: logging.Logger) -> Path | None:
    log.info("STAGE 01: discover (48h window) …")
    result = _run(["01_coindesk_discover.py"], log, "01")
    if result is None:
        return None

    stdout, stderr = result
    combined = stdout + stderr
    m = re.search(r"Output\s*:\s*(\S+discover_\S+\.json)", combined)
    if not m:
        log.error("STAGE 01: could not parse output path from stdout")
        return None

    path = Path(m.group(1))
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        n = len(entries)
    except Exception as e:
        log.error(f"STAGE 01: could not read output JSON: {e}")
        return None

    if n == 0:
        log.error("STAGE 01: discovered 0 articles — aborting")
        return None

    log.info(f"STAGE 01: discover → {n} articles → {path.name}")
    return path


def run_stage_dedup(log: logging.Logger, discover_json: Path) -> tuple:
    log.info("STAGE 04: dedup …")
    result = _run(["04_dedup.py", "--input", str(discover_json)], log, "04")
    if result is None:
        return None, 0, 0, 0

    stdout, stderr = result
    combined = stdout + stderr

    total = _parse_int(combined, r"Total input\s*:\s*(\d+)")
    skipped = _parse_int(combined, r"Skipped.*?:\s*(\d+)")
    new = _parse_int(combined, r"New.*?:\s*(\d+)")

    m = re.search(r"Output\s*:\s*(\S+discover_filtered_\S+\.json)", combined)
    if not m:
        log.error("STAGE 04: could not parse filtered output path")
        return None, 0, 0, 0

    return Path(m.group(1)), total, skipped, new


def write_last_run_marker(log: logging.Logger):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    LAST_RUN_FILE.write_text(ts + "\n", encoding="utf-8")
    log.info(f"Last run marker: {ts}")


def run_stage_scrape(log: logging.Logger, filtered_json: Path) -> tuple[int, int]:
    log.info(f"STAGE 02b: scrape ({filtered_json.name}) …")
    result = _run(
        ["02b_coindesk_scrape_fresh_context.py", "--input", str(filtered_json)],
        log, "02b",
    )
    if result is None:
        return 0, 0

    stdout, stderr = result
    combined = stdout + stderr

    ok_m = re.search(r"ok\s*:\s*(\d+)", combined)
    fail_m = re.search(r"failed\s*:\s*(\d+)", combined)
    n_ok = int(ok_m.group(1)) if ok_m else 0
    n_failed = int(fail_m.group(1)) if fail_m else 0
    return n_ok, n_failed


def run_stage_cleanup(log: logging.Logger) -> int:
    log.info("STAGE 03: cleanup …")
    result = _run(["03_coindesk_cleanup.py"], log, "03")
    if result is None:
        return 0

    stdout, stderr = result
    m = re.search(r"Files processed\s*:\s*(\d+)", stdout + stderr)
    return int(m.group(1)) if m else 0


def run_stage_publish(log: logging.Logger) -> tuple[int, int]:
    log.info("STAGE 05: publish …")
    result = _run(["05_publish.py"], log, "05")
    if result is None:
        return 0, 0

    stdout, stderr = result
    combined = stdout + stderr

    copied_m = re.search(r"(\d+)\s*article", combined)
    chunks_m = re.search(r"(\d+)\s*chunk", combined)
    n_copied = int(copied_m.group(1)) if copied_m else 0
    n_chunks = int(chunks_m.group(1)) if chunks_m else 0
    return n_copied, n_chunks


def _run(script_args: list[str], log: logging.Logger, stage_label: str) -> tuple[str, str] | None:
    cmd = [PYTHON] + script_args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PIPELINE_DIR),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        log.error(f"STAGE {stage_label}: timeout after 600s")
        return None
    except Exception as e:
        log.error(f"STAGE {stage_label}: subprocess error: {e}")
        return None

    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log.info(f"  [stdout] {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            log.info(f"  [stderr] {line}")

    if result.returncode != 0:
        log.error(f"STAGE {stage_label}: exit {result.returncode}")
        return None

    return result.stdout, result.stderr


def _parse_int(text: str, pattern: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


if __name__ == "__main__":
    main()
