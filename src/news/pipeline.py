# INFRASTRUCTURE
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import NEWS_DATA_ROOT, PROJECT_ROOT
from src.news.clean_pass import run_clean_pass
from src.news.engine.dedup import filter_new_entries
from src.news.engine.proxy_pool import box_lock
from src.news.engine.proxy_pool.janitor import Janitor
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.scrape import scrape_entries_proxy
from src.news.engine.scrape import RegwallGuardError, scrape_entries
from src.news.engine.scrape_job import append_to_raw_manifest, update_blocked_urls
from src.news.pipeline_support import (
    build_ok_manifest_entries, log_run_complete, master_list_path, persist_master_list,
    start_run, write_discover_snapshot, write_marker,
)
from src.news.platform import Platform


# ORCHESTRATOR

async def run_pipeline(platform: Platform, skip_index: bool = False) -> None:
    log = start_run(platform, "pipeline started")

    platform_dir, discover_dir, raw_dir = _prepare_pipeline_dirs(platform)

    if platform.scrape_engine == "proxy_pool":
        completed = await _run_pipeline_proxy_pool(platform, platform_dir, discover_dir, raw_dir, log)
    else:
        completed = await _run_pipeline_browser(platform, discover_dir, raw_dir, log)

    if completed:
        log_run_complete(log, platform, "pipeline complete")
        write_marker(platform.name, log)


# FUNCTIONS

def _prepare_pipeline_dirs(platform: Platform) -> tuple[Path, Path, Path]:
    platform_dir = NEWS_DATA_ROOT / platform.name
    discover_dir = platform_dir / "discover"
    raw_dir      = platform_dir / "raw"
    discover_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    return platform_dir, discover_dir, raw_dir


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
                write_marker(platform.name, log)
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
        write_marker(platform.name, log)
        return None
    if platform.uses_master_list:
        persist_master_list(entries, master_list_path(platform), log)
    else:
        discover_snapshot = write_discover_snapshot(entries, discover_dir)
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
    ok_manifest_entries = build_ok_manifest_entries(new_entries, manifest)
    append_to_raw_manifest(raw_dir, ok_manifest_entries)
    update_blocked_urls(discover_dir, manifest, {"dead": "dead_urls.txt", "failed": "failed_urls.txt"})

    if n_ok > 0:
        log.info(f"STAGE clean ({n_ok} ok entries) …")
        collection_dir = PROJECT_ROOT.parent / "rag-cli" / "data" / "documents" / platform.collection
        stats = run_clean_pass(platform, ok_manifest_entries, raw_dir, collection_dir, log)
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
        write_marker(platform.name, log)
        return False
    discover_snapshot = write_discover_snapshot(entries, discover_dir)
    log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")

    log.info("STAGE dedup …")
    new_entries, n_skip, _ = filter_new_entries(entries, raw_dir, platform.name, mode="raw")
    log.info(f"dedup → {len(entries)} total, {n_skip} already in raw, {len(new_entries)} new")
    if not new_entries:
        log.info("Nothing new to scrape — pipeline complete.")
        write_marker(platform.name, log)
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

    ok_manifest_entries = build_ok_manifest_entries(new_entries, manifest)
    append_to_raw_manifest(raw_dir, ok_manifest_entries)
    update_blocked_urls(raw_dir, manifest, {"regwall": "regwall_urls.txt", "empty": "empty_urls.txt"})
    n_ok = sum(1 for e in manifest if e.get("status") == "ok")
    log.info(f"scrape → {n_ok} ok, raw files persisted")
    return True
