#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import asyncio
import atexit
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

from src.config import LOG_DIR
from src.crawler.discovery import discover_urls_workflow
from src.log_janitor import get_retention_days
from src.scraper.chromium_scrape import scrape_url_chromium_workflow
from src.scraper.index_scrapes import index_scrapes_workflow
from src.search.browser import kill_own_chrome_atexit
from src.search.cache import cache_key, cache_read, format_engine_pool
from src.search.query_logger import log_query
from src.search.search_web import search_web_workflow

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "This CLI has no help text. Invoke one of the skills via the Skill tool "
    "and follow it exactly: websearch-web-research (web research and "
    "permanent capture), websearch-capture-and-index (capture-and-index "
    "pipeline), websearch-pdf (PDF to markdown to index). Do not guess flags."
)


# ORCHESTRATOR
def main():
    configure_logging()
    register_exit_hook()
    args = build_parser().parse_args()

    if args.cmd == "search_web":
        _dispatch_search_web(args)
    elif args.cmd == "search_engine_drilldown":
        _dispatch_search_engine_drilldown(args)
    elif args.cmd == "scrape_url_chromium":
        _dispatch_scrape_url_chromium(args)
    elif args.cmd == "discover_urls":
        _dispatch_discover_urls(args)
    elif args.cmd == "index_scrapes":
        _dispatch_index_scrapes(args)


# FUNCTIONS
def configure_logging() -> None:
    log_path = LOG_DIR / "cli.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_path, when="midnight", interval=1,
        backupCount=get_retention_days(), encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        handlers=[handler],
    )


def register_exit_hook() -> None:
    atexit.register(kill_own_chrome_atexit)


def build_parser() -> argparse.ArgumentParser:
    parser = NoHelpParser(
        prog="cli.py",
        description="websearch CLI — search_web, search_engine_drilldown, scrape_url_chromium, discover_urls, index_scrapes."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "search_web",
        help="Search across 8 engines. Returns engine breakdown table — use search_engine_drilldown to see URLs per engine."
    )
    p.add_argument("query", help="Search query (2-5 keywords)")

    p = sub.add_parser(
        "search_engine_drilldown",
        help="Show URL list for a specific engine from cached search results (or re-runs search on cache miss)."
    )
    p.add_argument("query", help="Search query (must match a prior search_web call)")
    p.add_argument("--engine", required=True,
                   help="Engine name: google, duckduckgo, mojeek, startpage, brave, bing, yandex, "
                        "openalex")

    p = sub.add_parser("scrape_url_chromium", help="Scrape URL to filtered markdown (PruningContentFilter, full content, no length cap).")
    p.add_argument("url", help="URL to scrape")

    p = sub.add_parser(
        "discover_urls",
        help="Discover a domain's URL set (robots/sitemap/navtree feeders); "
             "writes a pipe_scraper --url-file input."
    )
    p.add_argument("seed_url", help="Seed URL to start discovery from")
    p.add_argument("--url-file", required=True,
                   help="Path to write the discovered URL list (one per line, for pipe_scraper --url-file)")

    p = sub.add_parser(
        "index_scrapes",
        help="Index previously-scraped URLs into a RAG collection (reads each URL's own sidecar)."
    )
    p.add_argument("collection", help="Target RAG collection name")
    p.add_argument("urls", nargs="+", help="URL(s) previously scraped via scrape_url_chromium")

    return parser


class NoHelpParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, HELP_TEXT + "\n")

    def print_help(self, file=None):
        print(HELP_TEXT, file=file or sys.stderr)
        self.exit(2)


def _dispatch_search_web(args) -> None:
    result = asyncio.run(search_web_workflow(args.query, "en", None, None))
    print(result[0].text)


def _dispatch_search_engine_drilldown(args) -> None:
    key = cache_key(args.query, "en", None, None)
    hit = cache_read(key)
    cache_status = "hit"
    if hit is None:
        asyncio.run(search_web_workflow(args.query, "en", None, None))
        hit = cache_read(key)
        cache_status = "miss_then_searched" if hit is not None else "miss_then_search_failed"
    if hit is None:
        _log_drilldown(args.query, "en", args.engine, key, cache_status, False, [])
        print(f'# search_engine_drilldown: cache write failed for "{args.query}"')
        return
    pools = hit.get("pools", {})
    if args.engine not in pools:
        _log_drilldown(args.query, "en", args.engine, key, cache_status, False, [])
        avail = ", ".join(sorted(pools.keys())) or "(none)"
        print(f"Engine '{args.engine}' not in cached pools. Available: {avail}")
        return
    urls = [entry["url"] for entry in pools[args.engine]]
    _log_drilldown(args.query, "en", args.engine, key, cache_status, True, urls)
    print(format_engine_pool(pools[args.engine], args.engine, args.query))


def _log_drilldown(query, language, engine, search_key, cache_status, engine_in_pools, urls):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log_query({
        "record_type": "drilldown",
        "ts": ts,
        "query": query,
        "language": language,
        "engine": engine,
        "search_key": search_key,
        "cache_status": cache_status,
        "engine_in_pools": engine_in_pools,
        "result_count": len(urls),
        "urls": urls,
    })


def _dispatch_scrape_url_chromium(args) -> None:
    url = args.url
    if urlparse(url).path.lower().endswith(".pdf"):
        print(f"PDF must be downloaded by the user: {url}")
        return
    result = asyncio.run(scrape_url_chromium_workflow(url))
    print(result[0].text)


def _dispatch_discover_urls(args) -> None:
    result = asyncio.run(discover_urls_workflow(args.seed_url))
    _write_discovery_output(result, args.url_file)


def _write_discovery_output(result, url_file: str) -> None:
    if not result.ok:
        print(f"discover_urls FAILED: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"ok={result.ok} wall_s={result.wall_s:.1f}")
    print(f"failed_feeders: {result.failed_feeders}")
    print(f"dropped_malformed_urls: {result.dropped}")

    by_source = {}
    for u in result.urls:
        by_source[u.source] = by_source.get(u.source, 0) + 1
    scrape_urls = [u.url for u in result.urls]

    Path(url_file).write_text(("\n".join(scrape_urls) + "\n") if scrape_urls else "", encoding="utf-8")

    by_source_str = ", ".join(f"{k}={v}" for k, v in sorted(by_source.items()))
    print(f"total URLs: {len(result.urls)} (by source: {by_source_str})")
    print(f"url-file: {url_file} ({len(scrape_urls)} URLs written)")


def _dispatch_index_scrapes(args) -> None:
    result = index_scrapes_workflow(args.collection, args.urls)
    if not result.ok:
        print(f"index_scrapes FAILED: {result.error}", file=sys.stderr)
        sys.exit(1)
    for outcome in result.outcomes:
        print(_format_index_outcome(outcome))


def _format_index_outcome(outcome) -> str:
    if outcome.status == "indexed":
        return f"indexed: {outcome.url} -> {outcome.detail} ({outcome.byte_count} bytes)"
    if outcome.status == "no_sidecar":
        return f"no sidecar found: {outcome.url}"
    return f"failed: {outcome.url} ({outcome.detail})"


if __name__ == "__main__":
    main()
