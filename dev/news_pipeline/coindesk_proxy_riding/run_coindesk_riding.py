# INFRASTRUCTURE
import argparse
import asyncio
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager, load_backfill_pool
from p2_browser_rider import run_riding_pool
from p3_url_sampler import sample_urls
from p4_reporter import write_riding_report

BROWSER_ELIGIBLE_PROTOS = frozenset({"http", "socks5"})


# ORCHESTRATOR

async def _run(args: argparse.Namespace) -> None:
    _raise_fd_limit()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    url_queue  = _prepare_url_queue(args)
    proxy_pool = await _prepare_proxy_pool()

    cm          = PersistentCooldownManager()
    t_job_start = datetime.now(timezone.utc)
    t0          = time.monotonic()

    state = await run_riding_pool(
        url_queue=url_queue,
        proxy_pool=proxy_pool,
        cooldown_mgr=cm,
        output_dir=output_dir,
        burn_threshold=args.burn_threshold,
        n_slots=args.concurrency,
        page_timeout_ms=args.page_timeout,
        n_browsers=args.browsers,
        stall_timeout_s=args.stall_timeout,
    )

    elapsed = time.monotonic() - t0
    print(
        f"[main] done in {elapsed:.0f}s — "
        f"ok={state.n_ok} rw={state.n_regwall} fail={state.n_failed} "
        f"cf={state.n_connect_fail} termination={state.termination}",
        file=sys.stderr,
    )

    write_riding_report(state, output_dir, t_job_start)
    print(f"[main] report → {output_dir / 'job.md'}")


# FUNCTIONS

def _raise_fd_limit(target: int = 16_384) -> None:
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft   = target if hard == resource.RLIM_INFINITY else min(target, hard)
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
        soft2, hard2 = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"[main] RLIMIT_NOFILE soft={soft2} hard={hard2}", file=sys.stderr)
    except Exception as exc:
        print(
            f"[main] WARNING: could not raise RLIMIT_NOFILE: {exc}\n"
            f"  Manually run: ulimit -n 16384",
            file=sys.stderr,
        )


def _prepare_url_queue(args: argparse.Namespace) -> asyncio.Queue:
    urls = sample_urls(args.n_urls)
    if not urls:
        print(
            f"[main] FATAL: sample_urls({args.n_urls}) returned 0 URLs.\n"
            f"  INVENTORY_DIR resolution failed — check p3_url_sampler._repo_root().\n"
            f"  Expected: data/news/coindesk/inventory/ under repo root.",
            file=sys.stderr,
        )
        sys.exit(1)

    url_queue = asyncio.Queue()
    for u in urls:
        url_queue.put_nowait(u)
    print(
        f"[main] {len(urls)} URLs queued, concurrency={args.concurrency}, "
        f"browsers={args.browsers}, burn-threshold={args.burn_threshold}, page-timeout={args.page_timeout}ms",
        file=sys.stderr,
    )
    return url_queue


async def _prepare_proxy_pool() -> list:
    print("[main] loading proxy pool ...", file=sys.stderr)
    raw_pool, _ = await asyncio.get_running_loop().run_in_executor(None, load_backfill_pool)
    proxy_pool  = [(p, hp) for p, hp in raw_pool if p in BROWSER_ELIGIBLE_PROTOS]
    print(
        f"[main] pool: {len(raw_pool)} total, {len(proxy_pool)} browser-eligible (http+socks5)",
        file=sys.stderr,
    )
    return proxy_pool


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="CoinDesk browser-proxy riding scraper")
    ap.add_argument("--concurrency",    type=int, default=20,    help="Browser slots (default 20)")
    ap.add_argument("--burn-threshold", type=int, default=2,     help="Regwall hits before proxy rotate (default 2)")
    ap.add_argument("--n-urls",         type=int, default=500,   help="URLs to scrape (default 500)")
    ap.add_argument("--output-dir",     default="output",        help="Output directory for raw HTML + report")
    ap.add_argument("--page-timeout",   type=int, default=8_000, help="Playwright page timeout ms (default 8000)")
    ap.add_argument("--browsers",       type=int,   default=1,      help="Browser pool size (default 1)")
    ap.add_argument("--stall-timeout",  type=float, default=3_600.0, help="Stall watchdog threshold in seconds (default 3600)")
    return ap.parse_args()


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
