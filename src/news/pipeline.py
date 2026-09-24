# INFRASTRUCTURE
import dataclasses
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.news.platform import Platform
from src.news.engine.dedup import filter_new_entries
from src.news.engine.scrape import scrape_entries, RegwallGuardError
from src.news.engine.proxy_pool import box_lock
from src.news.engine.proxy_pool.janitor import Janitor
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.scrape import scrape_entries_proxy
from src.news.engine.scrape_job import scrape_chunks_raw, _append_to_raw_manifest, _update_blocked_urls
from src.news.engine.browser_reporter import write_scrape_report
from src.news.engine.proxy_riding.scrape import scrape_entries_riding, RidingScrapeConfig
from src.news.engine.proxy_riding.reporter import write_riding_report
from src.news.pipeline_support import (
    PROJECT_ROOT, LOG_DIR,
    _setup_logging, _check_internet, _persist_master_list, _write_discover_snapshot, _write_marker,
)
from src.news.clean_pass import _run_clean_pass

DATA_ROOT = PROJECT_ROOT / "data" / "news"
SCRAPE_CHUNK_SIZE = 200


# ORCHESTRATOR

async def run_discover_only(platform: Platform) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    log.info(f"=== {platform.name} discover-only started ===")
    if not _check_internet(platform, log):
        log.error("Internet check failed — aborting.")
        sys.exit(1)
    entries = await platform.discover()
    log.info(f"discover → {len(entries)} entries")
    if platform.uses_master_list:
        master_path = DATA_ROOT / platform.name / "discover" / "master_urls.txt"
        _persist_master_list(entries, master_path, log)
    _write_marker(platform.name, log)
    log.info(f"=== {platform.name} discover-only complete ===")


async def run_scrape_only(
    platform: Platform,
    year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
    skip_index: bool = False,
    n_browsers: int | None = None,
    n_slots: int | None = None,
    cooldown_policy: str | None = None,
    page_timeout_ms: int | None = None,
) -> None:
    log, job_id, filter_desc = _scrape_only_preamble(platform, year, from_date, to_date)

    entries = platform.load_scrape_entries(year=year, from_date=from_date, to_date=to_date, limit=limit)
    log.info(f"discover → {len(entries)} candidate URL(s) after filter")
    if not entries:
        log.info("No entries in date range — done.")
        _write_marker(platform.name, log)
        return

    raw_dir = DATA_ROOT / platform.name / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_ext = ".html" if platform.scrape_engine == "proxy_riding" else ".md"
    new_entries, n_skip, _ = filter_new_entries(entries, raw_dir, platform.name, mode="raw", raw_ext=raw_ext)
    log.info(f"dedup → {len(entries)} total, {n_skip} already in raw, {len(new_entries)} new")
    if not new_entries:
        log.info("All already in raw — done.")
        _write_marker(platform.name, log)
        return

    if platform.scrape_engine == "proxy_riding":
        await _run_scrape_only_riding(
            platform, new_entries, raw_dir, job_id,
            n_browsers, n_slots, cooldown_policy, page_timeout_ms, log,
        )
    else:
        await _run_scrape_only_browser(platform, new_entries, raw_dir, job_id, filter_desc, log)

    _write_marker(platform.name, log)
    log.info(f"=== {platform.name} scrape-only complete job_id={job_id} ===")


async def run_pipeline(platform: Platform, skip_index: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    log.info(f"=== {platform.name} pipeline started ===")

    if not _check_internet(platform, log):
        log.error("Internet check failed — aborting.")
        sys.exit(1)

    platform_dir = DATA_ROOT / platform.name
    discover_dir = platform_dir / "discover"
    raw_dir      = platform_dir / "raw"
    discover_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    if platform.scrape_engine == "proxy_pool":
        completed = await _run_pipeline_proxy_pool(platform, platform_dir, discover_dir, raw_dir, log)
    else:
        completed = await _run_pipeline_browser(platform, discover_dir, raw_dir, log)

    if completed:
        log.info(f"=== {platform.name} pipeline complete ===")
        _write_marker(platform.name, log)


# FUNCTIONS

def _scrape_only_preamble(
    platform: Platform, year: str | None, from_date: str | None, to_date: str | None,
) -> tuple[logging.Logger, str, str]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filter_desc = (
        f"year={year}" if year
        else f"from={from_date} to={to_date}" if (from_date or to_date)
        else "all"
    )
    log.info(f"=== {platform.name} scrape-only started job_id={job_id} filter={filter_desc} ===")
    if not _check_internet(platform, log):
        log.error("Internet check failed — aborting.")
        sys.exit(1)
    if not platform.supports_scrape_only:
        log.error(f"--scrape-only not supported for {platform.name} (no load_scrape_entries)")
        sys.exit(1)
    return log, job_id, filter_desc


async def _run_scrape_only_riding(
    platform:        Platform,
    new_entries:     list[dict],
    raw_dir:         Path,
    job_id:          str,
    n_browsers:      int | None,
    n_slots:         int | None,
    cooldown_policy: str | None,
    page_timeout_ms: int | None,
    log:             logging.Logger,
) -> None:
    riding_cfg = platform.riding_scrape_config or RidingScrapeConfig()
    overrides = {
        k: v for k, v in (
            ("n_browsers", n_browsers), ("n_slots", n_slots),
            ("cooldown_policy", cooldown_policy), ("page_timeout_ms", page_timeout_ms),
        ) if v is not None
    }
    if overrides:
        riding_cfg = dataclasses.replace(riding_cfg, **overrides)
    t_job_start  = datetime.now(timezone.utc)
    platform_dir = DATA_ROOT / platform.name
    job_dir      = DATA_ROOT / platform.name / "scrape_jobs" / job_id
    manifest, state = await scrape_entries_riding(new_entries, platform_dir, riding_cfg, job_dir)
    n_ok     = sum(1 for e in manifest if e["status"] == "ok")
    n_failed = sum(1 for e in manifest if e["status"] == "failed")
    wall_s   = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    log.info(
        f"=== scrape-only done (proxy_riding): ok={n_ok} failed={n_failed} wall={wall_s:.0f}s ==="
    )
    ok_manifest_entries = _build_ok_manifest_entries(new_entries, manifest)
    _append_to_raw_manifest(raw_dir, ok_manifest_entries)
    write_riding_report(state, job_dir, t_job_start)
    log.info(f"Job report written to {job_dir}")


async def _run_scrape_only_browser(
    platform:    Platform,
    new_entries: list[dict],
    raw_dir:     Path,
    job_id:      str,
    filter_desc: str,
    log:         logging.Logger,
) -> None:
    chunks = [new_entries[i:i + SCRAPE_CHUNK_SIZE] for i in range(0, len(new_entries), SCRAPE_CHUNK_SIZE)]
    log.info(f"chunked plan: {len(new_entries)} URLs → {len(chunks)} chunk(s) of {SCRAPE_CHUNK_SIZE}")

    t_job_start = datetime.now(timezone.utc)
    totals, job_records, regwall_abort = await scrape_chunks_raw(chunks, raw_dir, platform, log)

    wall_s  = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    rw_rate = totals["regwall"] / max(sum(totals.values()), 1)
    log.info(
        f"=== scrape-only done: ok={totals['ok']} regwall={totals['regwall']}({rw_rate:.1%}) "
        f"empty={totals['empty']} failed={totals['failed']} wall={wall_s:.0f}s"
        + (" [REGWALL ABORT]" if regwall_abort else "") + " ==="
    )
    job_dir = DATA_ROOT / platform.name / "scrape_jobs" / job_id
    write_scrape_report(job_dir, job_records, t_job_start, len(new_entries), filter_desc, regwall_abort)
    log.info(f"Job report written to {job_dir}")


async def _run_pipeline_proxy_pool(
    platform:     Platform,
    platform_dir: Path,
    discover_dir: Path,
    raw_dir:      Path,
    log:          logging.Logger,
) -> bool:
    log_dir    = platform_dir / "proxy_pool_logs"
    report_dir = platform_dir / "proxy_pool_reports"
    jobs_dir   = platform_dir / "proxy_pool_jobs"
    job_id     = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    manifest: list[dict] = []
    new_entries: list[dict] = []
    n_ok = 0

    with box_lock.acquire(job_id, f"{platform.name} discover+scrape"):
        j      = Janitor(jobs_dir, log_dir, report_dir)
        j.start_job(job_id)
        logger = AcquireLogger(total_urls=0, log_dir=log_dir)
        try:
            entries = await _stage_discover_proxy_pool(platform, discover_dir, log, logger)
            if entries is None:
                return False

            new_entries = _stage_dedup_proxy_pool(platform, entries, discover_dir, raw_dir, log)
            if not new_entries:
                log.info("Nothing new to scrape — pipeline complete.")
                _write_marker(platform.name, log)
                return False

            manifest, n_ok = _stage_scrape_proxy_pool(platform, new_entries, raw_dir, logger, log)

        finally:
            logger.close()
            j.end_job(job_id, logger._jsonl_path, len(new_entries), n_ok)

    _persist_proxy_pool_results(platform, new_entries, manifest, n_ok, raw_dir, discover_dir, log)
    return True


async def _stage_discover_proxy_pool(
    platform: Platform, discover_dir: Path, log: logging.Logger, logger: AcquireLogger,
) -> list[dict] | None:
    log.info("STAGE discover …")
    entries = await platform.discover(logger=logger)
    if not entries:
        log.error("discover returned 0 articles — aborting.")
        _write_marker(platform.name, log)
        return None
    if platform.uses_master_list:
        master_path = DATA_ROOT / platform.name / "discover" / "master_urls.txt"
        _persist_master_list(entries, master_path, log)
    else:
        discover_snapshot = _write_discover_snapshot(entries, discover_dir)
        log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")
    return entries


def _stage_dedup_proxy_pool(
    platform: Platform, entries: list[dict], discover_dir: Path, raw_dir: Path, log: logging.Logger,
) -> list[dict]:
    log.info("STAGE dedup …")
    failure_urls: set[str] = set()
    for _fname in ("dead_urls.txt", "failed_urls.txt"):
        _p = discover_dir / _fname
        if _p.exists():
            failure_urls |= {u for u in _p.read_text(encoding="utf-8").splitlines() if u}
    new_entries, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, platform.name, mode="raw",
        exclude_urls=failure_urls if failure_urls else None,
    )
    log.info(
        f"dedup → {len(entries)} total, {n_skip_raw} already in raw, "
        f"{n_excluded} known-failures excluded, {len(new_entries)} new"
    )
    return new_entries


def _stage_scrape_proxy_pool(
    platform: Platform, new_entries: list[dict], raw_dir: Path, logger: AcquireLogger, log: logging.Logger,
) -> tuple[list[dict], int]:
    log.info(f"STAGE scrape ({len(new_entries)} URLs) …")
    manifest = scrape_entries_proxy(new_entries, raw_dir, platform.proxy_scrape_config, logger)
    n_ok     = sum(1 for e in manifest if e["status"] == "ok")
    n_dead   = sum(1 for e in manifest if e["status"] == "dead")
    n_failed = sum(1 for e in manifest if e["status"] == "failed")
    log.info(f"scrape → {n_ok} ok, {n_dead} dead, {n_failed} failed")
    return manifest, n_ok


def _persist_proxy_pool_results(
    platform:     Platform,
    new_entries:  list[dict],
    manifest:     list[dict],
    n_ok:         int,
    raw_dir:      Path,
    discover_dir: Path,
    log:          logging.Logger,
) -> None:
    ok_manifest_entries = _build_ok_manifest_entries(new_entries, manifest)
    _append_to_raw_manifest(raw_dir, ok_manifest_entries)
    _update_blocked_urls(discover_dir, manifest, {"dead": "dead_urls.txt", "failed": "failed_urls.txt"})

    if n_ok > 0:
        log.info(f"STAGE clean ({n_ok} ok entries) …")
        collection_dir = PROJECT_ROOT.parent / "rag-cli" / "data" / "documents" / platform.collection
        stats = _run_clean_pass(platform, ok_manifest_entries, raw_dir, collection_dir, log)
        log.info(
            f"clean → {stats['n_cleaned']} cleaned, {stats['n_bodyless']} body-less, "
            f"{stats['total']} total → {collection_dir}"
        )


async def _run_pipeline_browser(
    platform:     Platform,
    discover_dir: Path,
    raw_dir:      Path,
    log:          logging.Logger,
) -> bool:
    log.info("STAGE discover …")
    entries = await platform.discover()
    if not entries:
        log.error("discover returned 0 articles — aborting.")
        _write_marker(platform.name, log)
        return False
    discover_snapshot = _write_discover_snapshot(entries, discover_dir)
    log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")

    log.info("STAGE dedup …")
    new_entries, n_skip, _ = filter_new_entries(entries, raw_dir, platform.name, mode="raw")
    log.info(f"dedup → {len(entries)} total, {n_skip} already in raw, {len(new_entries)} new")
    if not new_entries:
        log.info("Nothing new to scrape — pipeline complete.")
        _write_marker(platform.name, log)
        return False

    log.info(f"STAGE scrape ({len(new_entries)} URLs) …")
    manifest: list[dict] = []
    try:
        manifest = await scrape_entries(
            new_entries, raw_dir, platform.regwall_signals, platform.scrape_config
        )
    except RegwallGuardError as exc:
        manifest = exc.manifest
        log.error(f"STAGE scrape aborted — RegwallGuardError: {exc}")

    ok_manifest_entries = _build_ok_manifest_entries(new_entries, manifest)
    _append_to_raw_manifest(raw_dir, ok_manifest_entries)
    _update_blocked_urls(raw_dir, manifest, {"regwall": "regwall_urls.txt", "empty": "empty_urls.txt"})
    n_ok = sum(1 for e in manifest if e.get("status") == "ok")
    log.info(f"scrape → {n_ok} ok, raw files persisted")
    return True


def _build_ok_manifest_entries(new_entries: list[dict], manifest: list[dict]) -> list[dict]:
    entries_by_url = {e["url"]: e for e in new_entries}
    return [
        {
            "hash": e["hash"],
            "url": e["url"],
            "publication_date": entries_by_url.get(e["url"], {}).get("publication_date", ""),
        }
        for e in manifest if e.get("status") == "ok"
    ]
