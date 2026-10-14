# INFRASTRUCTURE
from pathlib import Path
from urllib.parse import urlsplit

from src.crawler.deep_dive_logger import log_deep_dive
from src.crawler.seed_feeders_scope import host_key
from src.scraper.scrape_logger import utc_timestamp


# FUNCTIONS

def log_discovery_record(seed_url: str, url_file: str, result) -> None:
    by_source: dict = {}
    for discovered in result.urls:
        by_source[discovered.source] = by_source.get(discovered.source, 0) + 1
    log_deep_dive({
        "record_type": "discovery", "ts": utc_timestamp(),
        "seed_url": seed_url, "host": host_of(seed_url),
        "url_file": url_file, "ok": result.ok, "error": result.error,
        "total": len(result.urls), "by_source": by_source,
        "failed_feeders": result.failed_feeders, "dropped": result.dropped,
        "wall_s": round(result.wall_s, 1),
    })


def log_scrape_round_record(
    run_id: str, urls: list[str], results: list[dict], onward_links: list[str] | None,
    engine: str, url_file: str | None, output_dir: Path, wall_s: float,
) -> None:
    log_deep_dive({
        "record_type": "scrape_round", "ts": utc_timestamp(),
        "run_id": run_id, "host": host_of(urls[0]) if urls else None,
        "engine": engine, "url_file": url_file, "output_dir": str(output_dir),
        "urls_requested": len(urls),
        "files_written": sum(1 for r in results if r["bytes"] > 0),
        "bytes": sum(r["bytes"] for r in results),
        "onward_links": None if onward_links is None else len(onward_links),
        "wall_s": round(wall_s, 1),
    })


def host_of(url: str) -> str | None:
    hostname = urlsplit(url).hostname
    return host_key(hostname) if hostname else None
