# INFRASTRUCTURE
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.news.platform import Platform
from src.news.engine.scrape import scrape_entries, RegwallGuardError


# ORCHESTRATOR

async def scrape_chunks_raw(
    chunks: list[list[dict]],
    raw_dir: Path,
    platform: "Platform",
    log: logging.Logger,
) -> tuple[dict, list[dict], bool]:
    totals = {"ok": 0, "regwall": 0, "empty": 0, "failed": 0}
    job_records: list[dict] = []
    regwall_abort = False
    raw_dir.mkdir(parents=True, exist_ok=True)
    for ci, chunk in enumerate(chunks):
        chunk_job_records, aborted = await _scrape_one_chunk(
            ci, len(chunks), chunk, raw_dir, platform, log, totals,
        )
        job_records += chunk_job_records
        if aborted:
            regwall_abort = True
            break
    return totals, job_records, regwall_abort


# FUNCTIONS

async def _scrape_one_chunk(
    ci:       int,
    n_chunks: int,
    chunk:    list[dict],
    raw_dir:  Path,
    platform: "Platform",
    log:      logging.Logger,
    totals:   dict,
) -> tuple[list[dict], bool]:
    log.info(f"CHUNK {ci + 1}/{n_chunks}: {len(chunk)} URLs …")
    t_chunk_start = datetime.now(timezone.utc)
    manifest: list[dict] = []
    aborted = False
    try:
        manifest = await scrape_entries(
            chunk, raw_dir, platform.regwall_signals, platform.scrape_config
        )
    except RegwallGuardError as exc:
        manifest = exc.manifest
        n_rw = sum(1 for e in manifest if e.get("status") == "regwall")
        log.error(
            f"RegwallGuardError chunk {ci + 1}: {exc} "
            f"(regwall rate {n_rw / max(len(chunk), 1):.1%} — stopping loop)"
        )
        aborted = True

    counts = {s: sum(1 for e in manifest if e.get("status") == s) for s in totals}
    for s, n in counts.items():
        totals[s] += n
    chunk_job_records = [{"t_chunk_start": t_chunk_start, **e} for e in manifest]

    entries_by_url = {e["url"]: e for e in chunk}
    ok_manifest_entries = [
        {
            "hash": e["hash"],
            "url": e["url"],
            "publication_date": entries_by_url.get(e["url"], {}).get("publication_date", ""),
        }
        for e in manifest if e.get("status") == "ok"
    ]
    _append_to_raw_manifest(raw_dir, ok_manifest_entries)
    _update_blocked_urls(raw_dir, manifest, {"regwall": "regwall_urls.txt", "empty": "empty_urls.txt"})

    log.info(
        f"  chunk {ci + 1}: ok={counts['ok']} "
        f"regwall={counts['regwall']}({counts['regwall'] / max(len(chunk), 1):.0%}) "
        f"empty={counts['empty']} failed={counts['failed']}"
    )
    return chunk_job_records, aborted

def _append_to_raw_manifest(raw_dir: Path, ok_entries: list[dict]) -> None:
    if not ok_entries:
        return
    manifest_path = raw_dir / "manifest.jsonl"
    with open(manifest_path, "a", encoding="utf-8") as f:
        for entry in ok_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _update_blocked_urls(raw_dir: Path, manifest: list[dict], status_filenames: dict[str, str]) -> None:
    for status, filename in status_filenames.items():
        new_urls = {e["url"] for e in manifest if e.get("status") == status}
        if not new_urls:
            continue
        path = raw_dir / filename
        existing = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
        merged = (existing | new_urls) - {""}
        path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")

