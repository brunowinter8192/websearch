#!/usr/bin/env python3

# INFRASTRUCTURE

import argparse
import asyncio
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi.requests import AsyncSession

sys.path.insert(0, str(Path(__file__).parent))
from probe_pool_size import HTTP_SOURCES, SOCKS4_SOURCES, SOCKS5_SOURCES, fetch_all_sources
from monosans_loader import load_monosans_proxies
from proxy_status_log import record_run, partition_fresh
from curated_sources import (
    load_curated_proxies, load_thespeedx_proxies,
    load_databay_proxies, load_jetkai_proxies, load_roosterkid_proxies,
)

from _probe_liveness_classify import check_proxy
from _probe_liveness_report import (
    print_console_summary, append_sweep_log, write_unknown_log,
)

SCRIPT_DIR  = Path(__file__).parent
FROZEN_DIR  = SCRIPT_DIR / "frozen_pool"

SAMPLE_SEED = 42

EVAL_ONLY_SOURCES = {"thespeedx", "databay", "jetkai", "roosterkid"}

FILTERED_LOADERS = {"monosans": load_monosans_proxies, "curated": load_curated_proxies}

EVAL_LOADERS = {
    "thespeedx":  ("TheSpeedX",  load_thespeedx_proxies),
    "databay":    ("databay",    load_databay_proxies),
    "jetkai":     ("jetkai",     load_jetkai_proxies),
    "roosterkid": ("roosterkid", load_roosterkid_proxies),
}

# ORCHESTRATOR

async def probe_liveness_workflow() -> None:
    args = parse_args()

    if args.freeze:
        await freeze_pool()
        return

    entries, mode, skipped_count = load_entries(args)

    ts      = datetime.now(timezone.utc)
    t0_wall = time.monotonic()

    results = await run_checks(
        entries,
        concurrency=args.concurrency,
        connect_s=args.connect_timeout,
        read_s=args.read_timeout,
    )

    elapsed       = time.monotonic() - t0_wall
    print_console_summary(results, args.concurrency, elapsed)
    append_sweep_log(
        results, ts, mode, len(entries),
        args.concurrency, args.connect_timeout, args.read_timeout, elapsed,
        skipped=skipped_count,
    )
    if any(r["bucket"] == "unknown" for r in results):
        write_unknown_log(results, ts)
    if args.source not in EVAL_ONLY_SOURCES:
        record_run(results, mode)


# FUNCTIONS

def load_entries(args: argparse.Namespace) -> tuple[list[tuple[str, str]], str, int]:
    if args.source in FILTERED_LOADERS:
        return load_filtered_entries(args, FILTERED_LOADERS[args.source])
    if args.source in EVAL_LOADERS:
        return load_eval_entries(args.source, *EVAL_LOADERS[args.source])
    return load_frozen_entries(args)


def load_filtered_entries(args: argparse.Namespace, loader) -> tuple[list[tuple[str, str]], str, int]:
    entries = loader()
    to_check, skipped_fresh = partition_fresh(entries, args.recheck_window)
    print(f"Freshness filter: {len(to_check)} to check, {len(skipped_fresh)} skipped (last_seen < {args.recheck_window}s ago)")
    return to_check, args.source, len(skipped_fresh)


def load_eval_entries(source: str, label: str, loader) -> tuple[list[tuple[str, str]], str, int]:
    entries = loader()
    print(f"{label} eval: {len(entries)} proxies (no freshness filter, no log write)")
    return entries, source, 0


def load_frozen_entries(args: argparse.Namespace) -> tuple[list[tuple[str, str]], str, int]:
    entries = load_frozen_pool(Path(args.input))
    if args.sample:
        return build_sample(entries, args.sample, args.seed), "sample", 0
    return entries, "full", 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Proxy liveness checker + concurrency sweep")
    p.add_argument("--freeze", action="store_true", help="Fetch 68 sources, write frozen_pool/")
    p.add_argument("--source", choices=["frozen", "monosans", "curated", "thespeedx", "databay", "jetkai", "roosterkid"],
                   default="frozen",
                   help="Proxy source: frozen/monosans/curated (log-writing) or thespeedx/databay/jetkai/roosterkid (eval-only)")
    p.add_argument("--sample", type=int, metavar="N", help="Check N random proxies (seeded)")
    p.add_argument("--full", action="store_true", help="Check full frozen pool")
    p.add_argument("--seed", type=int, default=SAMPLE_SEED, help=f"RNG seed (default {SAMPLE_SEED})")
    p.add_argument("--concurrency", type=int, default=512, help="Semaphore size (default 512)")
    p.add_argument("--connect-timeout", type=float, default=5.0, metavar="S")
    p.add_argument("--read-timeout",    type=float, default=5.0, metavar="S")
    p.add_argument("--input", default=str(FROZEN_DIR), help="Frozen pool dir")
    p.add_argument("--recheck-window", type=int, default=3600, metavar="S",
                   help="Skip monosans proxies whose last check is younger than S seconds (default 3600)")
    return p.parse_args()


async def freeze_pool() -> None:
    print("=== freeze: fetching 68 sources ===")
    t0 = time.monotonic()
    source_results = await fetch_all_sources()
    elapsed = time.monotonic() - t0

    bucket_proxies: dict[str, set[str]] = {"http": set(), "socks4": set(), "socks5": set()}
    for r in source_results:
        bucket_proxies[r["bucket"]].update(r["proxies"])

    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    for bucket, proxies in bucket_proxies.items():
        path = FROZEN_DIR / f"{bucket}.txt"
        path.write_text("\n".join(sorted(proxies)) + "\n", encoding="utf-8")
        print(f"  {bucket:8}: {len(proxies):>8,} unique → {path.name}")

    ok    = sum(1 for r in source_results if r["ok"])
    total = sum(len(p) for p in bucket_proxies.values())
    print(f"\nFrozen: {total:,} unique total | {ok}/{len(source_results)} sources OK | {elapsed:.1f}s")


def load_frozen_pool(frozen_dir: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto in ("http", "socks4", "socks5"):
        path = frozen_dir / f"{proto}.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append((proto, line))
    return entries


def build_sample(entries: list[tuple[str, str]], n: int, seed: int) -> list[tuple[str, str]]:
    return random.Random(seed).sample(entries, min(n, len(entries)))


async def run_checks(
    entries: list[tuple[str, str]],
    concurrency: int,
    connect_s: float,
    read_s: float,
) -> list[dict]:
    sem     = asyncio.Semaphore(concurrency)
    results: list[dict | None] = [None] * len(entries)
    done    = [0]
    total   = len(entries)

    print(f"Checking {total:,} proxies  concurrency={concurrency}  "
          f"connect={connect_s}s  read={read_s}s ...")

    async with AsyncSession() as session:
        async def _one(i: int, proto: str, host_port: str) -> None:
            results[i] = await check_proxy(session, sem, proto, host_port, connect_s, read_s)
            done[0] += 1
            n = done[0]
            if n % 2000 == 0 or n == total:
                alive_so_far = sum(1 for r in results[:n] if r and r["alive"])
                print(f"  {n:>6}/{total}  alive={alive_so_far}", flush=True)

        await asyncio.gather(*[_one(i, proto, hp) for i, (proto, hp) in enumerate(entries)])

    return results


if __name__ == "__main__":
    asyncio.run(probe_liveness_workflow())
