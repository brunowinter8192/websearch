# INFRASTRUCTURE
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import box_lock
import p7_janitor as janitor
from p2_cooldown import PersistentCooldownManager
from p3_target import build_sitemap_target, _LOC_RE
from p4_loop import run_loop, REFRESH_INTERVAL_S
from p5_logger import AcquireLogger
from p6_buffer import BUFFER_SIZE, DEFAULT_CONCURRENCY

sys.path.insert(0, str(Path(__file__).parent.parent))
from curated_sources import load_backfill_pool
from proxy_rejections import print_rejections

ACQUIRE_BASE      = Path(__file__).parent
OUTPUT_DIR        = ACQUIRE_BASE / "acquire_pipe_output"
LOG_DIR           = ACQUIRE_BASE / "acquire_pipe_logs"
ARTICLE_URLS_FILE = OUTPUT_DIR / "theblock_article_urls.txt"


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire-pipe (sustained): sitemap dev-run → ~27k article URLs"
    )
    _add_arguments(parser)
    args = parser.parse_args()
    acquire_pipe_workflow(
        concurrency=args.concurrency,
        buffer_size=args.buffer_size,
    )
    print_rejections()


# FUNCTIONS

def _add_arguments(parser):
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help=f"Concurrent (proxy, URL) pairs per batch (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--buffer_size", type=int, default=BUFFER_SIZE,
        help=f"Active proxy buffer depth (default: {BUFFER_SIZE})",
    )


def acquire_pipe_workflow(
    concurrency: int,
    buffer_size: int,
) -> None:
    cm           = PersistentCooldownManager()
    initial_pool = load_backfill_pool()
    print(f"[acquire_pipe] Loaded backfill pool: {len(initial_pool)} proxies")
    print(f"[acquire_pipe] Building sitemap target...")
    target_urls = build_sitemap_target(pool=initial_pool)
    print(f"[acquire_pipe] Target: {len(target_urls)} sub-sitemaps")

    job_id      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_desc = f"theblock-{len(target_urls)}"

    try:
        with box_lock.acquire(job_id, target_desc):
            _run_job(job_id, target_urls, initial_pool, cm, concurrency, buffer_size)

    except box_lock.LockBusyError as e:
        print(e)
        sys.exit(1)


def _run_job(
    job_id: str,
    target_urls: list[str],
    initial_pool: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    concurrency: int,
    buffer_size: int,
) -> None:
    janitor.start_job(job_id)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loc_urls: list[str] = []
    logger = AcquireLogger(total_urls=len(target_urls), log_dir=LOG_DIR)

    content_handler = _make_content_handler(loc_urls)

    print(
        f"[acquire_pipe] Starting sustained loop "
        f"(concurrency={concurrency}, buffer={buffer_size})..."
    )
    _pool_provider = _make_pool_provider(initial_pool)

    done, dead, gap = run_loop(
        _pool_provider, target_urls, "xml", logger, cm,
        concurrency=concurrency,
        buffer_size=buffer_size,
        content_handler=content_handler,
    )
    print(f"[acquire_pipe] Loop done: {len(done)} completed, {len(gap)} remaining")
    print(f"[acquire_pipe] {len(dead)} URLs permanently dead (404/410)")

    _write_article_urls(loc_urls)

    logger.close()
    janitor.end_job(job_id, logger._jsonl_path, len(target_urls), len(done))
    print(f"[acquire_pipe] Job report: acquire_pipe_jobs/{job_id}/")

    if gap:
        print(f"[acquire_pipe] {len(gap)} sub-sitemaps incomplete")


def _make_content_handler(loc_urls: list[str]):
    def content_handler(url: str, content: bytes) -> None:
        fname = OUTPUT_DIR / _url_to_filename(url)
        fname.write_bytes(b"<!-- source: " + url.encode() + b" -->\n" + content)
        for m in _LOC_RE.finditer(content):
            loc_urls.append(m.group(1).decode().strip())
    return content_handler


def _make_pool_provider(initial_pool: list[tuple[str, str]]):
    _used = [False]
    def _pool_provider():
        if not _used[0]:
            _used[0] = True
            return initial_pool
        return load_backfill_pool()
    return _pool_provider


def _write_article_urls(loc_urls: list[str]) -> None:
    article_urls = list(dict.fromkeys(loc_urls))
    ARTICLE_URLS_FILE.write_text("\n".join(article_urls) + "\n", encoding="utf-8")
    print(f"[acquire_pipe] Article URLs: {len(article_urls)} unique → {ARTICLE_URLS_FILE}")


def _url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:100]
    return f"{slug}.xml"


if __name__ == "__main__":
    main()
