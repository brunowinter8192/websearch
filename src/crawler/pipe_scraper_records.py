# INFRASTRUCTURE
from src.crawler.pipe_scrape_logger import log_pipe_scrape

# FUNCTIONS

def log_pipe_record(
    run_ctx: dict, ts: str, url: str, domain: str,
    status: int | None, byte_count: int, wall_ms: int, diagnosis: dict,
    landed_url: str | None = None,
    error: str | None = None,
) -> None:
    log_pipe_scrape({
        "ts": ts, "run_id": run_ctx["run_id"], "url": url, "domain": domain,
        "http_status": status, "bytes": byte_count, "wall_ms": wall_ms,
        "engine": "chromium",
        "crawl4ai_success": diagnosis.get("crawl4ai_success"),
        "crawl4ai_error_message": diagnosis.get("crawl4ai_error_message"),
        "crawl4ai_attempts": diagnosis.get("crawl4ai_attempts"),
        "crawl4ai_resolved_by": diagnosis.get("crawl4ai_resolved_by"),
        "crawl4ai_fallback_fetch_used": diagnosis.get("crawl4ai_fallback_fetch_used"),
        "landed_url": landed_url,
        "error": error,
        "config_hash": run_ctx["config_hash"], "config": run_ctx["config"],
    })

def log_pipe_camoufox_record(
    run_ctx: dict, ts: str, url: str, domain: str,
    status: int | None, byte_count: int, wall_ms: int, meta: dict,
) -> None:
    log_pipe_scrape({
        "ts": ts, "run_id": run_ctx["run_id"], "url": url, "domain": domain,
        "http_status": status, "bytes": byte_count, "wall_ms": wall_ms,
        "engine": "camoufox",
        "acquisition_error": meta.get("acquisition_error"),
        "landed_url": meta.get("landed_url"),
        "markdown_conversion_error": meta.get("markdown_conversion_error"),
        "document_status_chain": meta.get("document_status_chain"),
        "config_hash": meta.get("config_hash"), "config": meta.get("config"),
    })
