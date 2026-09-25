# INFRASTRUCTURE
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig

sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager
from _p2_fetch import RAW_SUBDIR, _fetch_one_url, _url_hash, _write_raw
from _p2_state import JobRecord, RideRecord, RiderState, STALL_TIMEOUT_S
from _p2_watchdog import _abort_stall, _watchdog
import json

PAGE_TIMEOUT_MS   = 8_000
FAIL_THRESHOLD    = 2


# ORCHESTRATOR

def main() -> None:
    load_backfill_pool = _import_pool_loader()
    sample_urls = _import_url_sampler()

    N_URLS    = 5
    N_SLOTS   = 4
    TIMEOUT_S = 300

    smoke = _run_rider_smoke(load_backfill_pool, sample_urls, N_URLS, N_SLOTS, TIMEOUT_S)

    asyncio.run(smoke())


# FUNCTIONS

def _import_pool_loader():
    from p0_pool import load_backfill_pool
    return load_backfill_pool


def _import_url_sampler():
    from p3_url_sampler import sample_urls
    return sample_urls


def _run_rider_smoke(load_backfill_pool, sample_urls, N_URLS, N_SLOTS, TIMEOUT_S):
    async def smoke() -> None:
        print("[smoke] loading proxy pool ...", file=sys.stderr)
        pool, _ = await asyncio.get_running_loop().run_in_executor(None, load_backfill_pool)
        print(f"[smoke] pool: {len(pool)} raw proxies", file=sys.stderr)

        cm        = PersistentCooldownManager()
        urls      = sample_urls(500)[:N_URLS]
        url_queue = asyncio.Queue()
        [url_queue.put_nowait(u) for u in urls]
        print(f"[smoke] {N_URLS} URLs / {N_SLOTS} slots:", file=sys.stderr)
        [print(f"  {u}", file=sys.stderr) for u in urls]

        out_dir = Path(__file__).parent / "smoke_output"
        t0      = time.monotonic()

        try:
            state = await asyncio.wait_for(
                run_riding_pool(url_queue, pool, cm, out_dir,
                                burn_threshold=2, n_slots=N_SLOTS, page_timeout_ms=8000),
                timeout=TIMEOUT_S,
            )
            state_timeout = False
        except asyncio.TimeoutError:
            print("[smoke] TIMEOUT — partial results follow", file=sys.stderr)
            state_timeout = True
            state = None

        elapsed   = time.monotonic() - t0
        raw_dir   = out_dir / "raw"
        raw_files = sorted(raw_dir.glob("*.html")) if raw_dir.exists() else []

        report = {
            "elapsed_s":      round(elapsed, 1),
            "timeout":        state_timeout,
            "n_ok":           state.n_ok           if state else "?",
            "n_regwall":      state.n_regwall       if state else "?",
            "n_failed":       state.n_failed        if state else "?",
            "n_connect_fail": state.n_connect_fail  if state else "?",
            "termination":    state.termination     if state else "timeout",
            "proxies_used":   len(state.ride_records) if state else "?",
            "raw_files":      len(raw_files),
        }
        print(json.dumps(report, indent=2))
        for f in raw_files[:3]:
            print(f"  raw/{f.name}: {f.stat().st_size:,} bytes")
    return smoke


async def run_riding_pool(
    url_queue:       asyncio.Queue,
    proxy_pool:      list,
    cooldown_mgr:    PersistentCooldownManager,
    output_dir:      Path,
    burn_threshold:  int,
    n_slots:         int,
    page_timeout_ms: int   = PAGE_TIMEOUT_MS,
    n_browsers:      int   = 1,
    stall_timeout_s: float = STALL_TIMEOUT_S,
) -> RiderState:
    (output_dir / RAW_SUBDIR).mkdir(parents=True, exist_ok=True)
    state = RiderState(
        url_queue=url_queue,
        proxy_pool=proxy_pool,
        cooldown_mgr=cooldown_mgr,
        output_dir=output_dir,
        burn_threshold=burn_threshold,
        page_timeout_ms=page_timeout_ms,
        total_urls=url_queue.qsize(),
        stall_timeout_s=stall_timeout_s,
    )
    state.n_browsers = n_browsers
    state.n_slots    = n_slots
    crawlers = [AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) for _ in range(n_browsers)]
    await asyncio.gather(*[c.start() for c in crawlers])
    watchdog = asyncio.create_task(_watchdog(state, output_dir))
    try:
        tasks = [asyncio.create_task(_run_slot(i, crawlers[i % n_browsers], state)) for i in range(n_slots)]
        await asyncio.gather(*tasks)
    finally:
        watchdog.cancel()
        results = await asyncio.gather(*[c.close() for c in crawlers], return_exceptions=True)
        for idx, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"[rider] crawler[{idx}].close warn: {r}", file=sys.stderr)
    if state.termination == "running":
        state.termination = "all-done"
    return state


async def _run_slot(slot_id: int, crawler: AsyncWebCrawler, state: RiderState) -> None:
    print(f"[slot {slot_id}] started", file=sys.stderr)

    while not state.all_resolved:
        if time.monotonic() - state.last_progress_mono > state.stall_timeout_s:
            print(f"[slot {slot_id}] stall — stopping", file=sys.stderr)
            state.termination = "stall"
            break

        entry = await _next_proxy(state)
        if entry is None:
            if state.all_resolved:
                break
            print(f"[slot {slot_id}] pool exhausted", file=sys.stderr)
            state.termination = "pool-exhausted"
            break

        proto, hp = entry
        await _ride_one_proxy(slot_id, crawler, state, proto, hp)

    print(f"[slot {slot_id}] exit", file=sys.stderr)


async def _next_proxy(state: RiderState) -> tuple[str, str] | None:
    async with state.proxy_lock:
        eligible = state.cooldown_mgr.eligible_candidates(state.proxy_pool)
        if not eligible:
            return None
        idx              = state.proxy_cursor % len(eligible)
        state.proxy_cursor += 1
        return eligible[idx]


async def _ride_one_proxy(slot_id: int, crawler: AsyncWebCrawler, state: RiderState, proto: str, hp: str) -> None:
    pstr   = f"{proto}://{hp}"
    t_bind = time.monotonic()
    ride   = {"burn_count": 0, "fail_count": 0, "ride_ok": 0, "positions": [], "cf_broke": False}

    try:
        while ride["burn_count"] < state.burn_threshold:
            if state.all_resolved:
                break
            if time.monotonic() - state.last_progress_mono > state.stall_timeout_s:
                state.termination = "stall"
                break

            url = await _get_next_queue_url(state)
            if url is None:
                if state.all_resolved:
                    break
                continue

            if await _ride_one_url(slot_id, state, crawler, pstr, url, ride):
                break

    finally:
        _finalize_ride(slot_id, state, pstr, proto, hp, t_bind, ride)


async def _get_next_queue_url(state: RiderState) -> str | None:
    try:
        return await asyncio.wait_for(state.url_queue.get(), timeout=10.0)
    except asyncio.TimeoutError:
        return None


async def _ride_one_url(slot_id: int, state: RiderState, crawler: AsyncWebCrawler,
                         pstr: str, url: str, ride: dict) -> bool:
    state.in_flight += 1
    state.in_flight_urls.add(url)
    ride_pos  = len(ride["positions"]) + 1
    t_url_abs = datetime.now(timezone.utc)

    status, char_count, markdown_len, elapsed, html, err = await _fetch_one_url(
        crawler, url, pstr, state.page_timeout_ms,
    )
    state.in_flight -= 1
    state.in_flight_urls.discard(url)

    ride["positions"].append((url, status, round(elapsed, 2)))
    job = JobRecord(
        url=url, url_hash=_url_hash(url),
        status=status, char_count=char_count, markdown_len=markdown_len,
        elapsed_s=round(elapsed, 2), error=err, file=None,
        t_start=t_url_abs, ride_position=ride_pos, proxy_str=pstr,
    )

    should_break = _apply_url_status(slot_id, state, url, html, ride, job, ride_pos)
    if not should_break:
        state.job_records.append(job)
    return should_break


def _finalize_ride(slot_id: int, state: RiderState, pstr: str, proto: str, hp: str,
                    t_bind: float, ride: dict) -> None:
    r = RideRecord(
        proxy_str=pstr, proto=proto, host_port=hp,
        n_ok=ride["ride_ok"], n_regwall=ride["burn_count"],
        n_connect_fail=1 if ride["cf_broke"] else 0,
        n_failed=ride["fail_count"],
        n_urls_attempted=len(ride["positions"]),
        burned_threshold=ride["burn_count"] >= state.burn_threshold,
        burned_connect=ride["cf_broke"],
        ride_s=time.monotonic() - t_bind,
        positions=ride["positions"],
    )
    state.ride_records.append(r)
    state.cooldown_mgr.mark_burned(proto, hp)
    print(
        f"[slot {slot_id}] proxy done ok={ride['ride_ok']} rw={ride['burn_count']}"
        f" cf={int(ride['cf_broke'])} n={len(ride['positions'])} {pstr}",
        file=sys.stderr,
    )


def _apply_url_status(slot_id: int, state: RiderState, url: str, html: str,
                       ride: dict, job: JobRecord, ride_pos: int) -> bool:
    status = job.status
    should_break = False

    if status == "ok":
        out      = _write_raw(_url_hash(url), html, state.output_dir)
        job.file = str(out)
        state.n_ok += 1
        ride["ride_ok"] += 1
        state.last_progress_mono = time.monotonic()
        print(f"[slot {slot_id}] ok  r={ride_pos} {url[:70]}", file=sys.stderr)

    elif status == "regwall":
        ride["burn_count"] += 1
        state.n_regwall += 1
        state.url_queue.put_nowait(url)
        print(
            f"[slot {slot_id}] RW  burn={ride['burn_count']}/{state.burn_threshold}"
            f" r={ride_pos}", file=sys.stderr,
        )

    elif status == "connect_fail":
        state.n_connect_fail += 1
        state.url_queue.put_nowait(url)
        ride["cf_broke"] = True
        print(f"[slot {slot_id}] CF  rotating", file=sys.stderr)
        should_break = True

    else:
        ride["fail_count"] += 1
        state.url_queue.put_nowait(url)
        print(
            f"[slot {slot_id}] {status} fail={ride['fail_count']}/{FAIL_THRESHOLD}"
            f" r={ride_pos} → requeue", file=sys.stderr,
        )
        if ride["fail_count"] >= FAIL_THRESHOLD:
            should_break = True

    return should_break


if __name__ == "__main__":
    main()
