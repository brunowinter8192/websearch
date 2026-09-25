# INFRASTRUCTURE
import dataclasses
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import LOG_DIR, NEWS_DATA_ROOT
from src.news.engine.browser_reporter import write_scrape_report
from src.news.engine.dedup import filter_new_entries
from src.news.engine.proxy_riding.reporter import write_riding_report
from src.news.engine.proxy_riding.scrape import RidingScrapeConfig, scrape_entries_riding
from src.news.engine.scrape_job import append_to_raw_manifest, scrape_chunks_raw
from src.news.pipeline_support import (
    build_ok_manifest_entries, require_internet, setup_logging, write_marker,
)
from src.news.platform import Platform

SCRAPE_CHUNK_SIZE = 200


# ORCHESTRATOR

async def scrape_only_workflow(
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

    entries = _load_candidates(platform, year, from_date, to_date, limit, log)
    if not entries:
        _finish_without_scrape(platform, log, "No entries in date range — done.")
        return

    raw_dir = _prepare_raw_dir(platform)
    new_entries = _dedup_against_raw(platform, entries, raw_dir, log)
    if not new_entries:
        _finish_without_scrape(platform, log, "All already in raw — done.")
        return

    if platform.scrape_engine == "proxy_riding":
        await _run_scrape_only_riding(
            platform, new_entries, raw_dir, job_id,
            n_browsers, n_slots, cooldown_policy, page_timeout_ms, log,
        )
    else:
        await _run_scrape_only_browser(platform, new_entries, raw_dir, job_id, filter_desc, log)

    write_marker(platform.name, log)
    _log_scrape_only_complete(log, platform, job_id)


# FUNCTIONS

def _scrape_only_preamble(
    platform: Platform, year: str | None, from_date: str | None, to_date: str | None,
) -> tuple[logging.Logger, str, str]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = setup_logging(platform.name)
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filter_desc = (
        f"year={year}" if year
        else f"from={from_date} to={to_date}" if (from_date or to_date)
        else "all"
    )
    log.info(f"=== {platform.name} scrape-only started job_id={job_id} filter={filter_desc} ===")
    require_internet(platform, log)
    if not platform.supports_scrape_only:
        log.error(f"--scrape-only not supported for {platform.name} (no load_scrape_entries)")
        sys.exit(1)
    return log, job_id, filter_desc


def _load_candidates(
    platform: Platform,
    year: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int | None,
    log: logging.Logger,
) -> list[dict]:
    entries = platform.load_scrape_entries(year=year, from_date=from_date, to_date=to_date, limit=limit)
    log.info(f"discover → {len(entries)} candidate URL(s) after filter")
    return entries


def _finish_without_scrape(platform: Platform, log: logging.Logger, message: str) -> None:
    log.info(message)
    write_marker(platform.name, log)


def _prepare_raw_dir(platform: Platform) -> Path:
    raw_dir = NEWS_DATA_ROOT / platform.name / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _dedup_against_raw(
    platform: Platform, entries: list[dict], raw_dir: Path, log: logging.Logger,
) -> list[dict]:
    raw_ext = ".html" if platform.scrape_engine == "proxy_riding" else ".md"
    new_entries, n_skip, _ = filter_new_entries(entries, raw_dir, platform.name, mode="raw", raw_ext=raw_ext)
    log.info(f"dedup → {len(entries)} total, {n_skip} already in raw, {len(new_entries)} new")
    return new_entries


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
    platform_dir = NEWS_DATA_ROOT / platform.name
    job_dir      = NEWS_DATA_ROOT / platform.name / "scrape_jobs" / job_id
    manifest, state = await scrape_entries_riding(new_entries, platform_dir, riding_cfg, job_dir)
    n_ok     = sum(1 for e in manifest if e["status"] == "ok")
    n_failed = sum(1 for e in manifest if e["status"] == "failed")
    wall_s   = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    log.info(
        f"=== scrape-only done (proxy_riding): ok={n_ok} failed={n_failed} wall={wall_s:.0f}s ==="
    )
    ok_manifest_entries = build_ok_manifest_entries(new_entries, manifest)
    append_to_raw_manifest(raw_dir, ok_manifest_entries)
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
    job_dir = NEWS_DATA_ROOT / platform.name / "scrape_jobs" / job_id
    write_scrape_report(job_dir, job_records, t_job_start, len(new_entries), filter_desc, regwall_abort)
    log.info(f"Job report written to {job_dir}")


def _log_scrape_only_complete(log: logging.Logger, platform: Platform, job_id: str) -> None:
    log.info(f"=== {platform.name} scrape-only complete job_id={job_id} ===")
