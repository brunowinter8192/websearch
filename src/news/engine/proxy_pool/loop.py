# INFRASTRUCTURE

import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from src.news.engine.proxy_pool.fetch import fetch_url
from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.buffer import build_active_buffer, refill_buffer, BUFFER_SIZE, DEFAULT_CONCURRENCY

_sleep             = time.sleep
REFRESH_INTERVAL_S = 3600
STALL_TIMEOUT_S    = 3600


# ORCHESTRATOR

# Sustained concurrent rotation loop: 60-min pool refresh + wait-on-exhaustion; returns (done, dead, gap).
def run_loop(
    pool_provider: Callable[[], tuple[list[tuple[str, str]], list[dict]]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    concurrency: int = DEFAULT_CONCURRENCY,
    buffer_size: int = BUFFER_SIZE,
    content_handler: Callable[[str, bytes], None] | None = None,
    refresh_interval_s: float = REFRESH_INTERVAL_S,
) -> tuple[list[str], list[str], list[str]]:
    queue         = deque(target_urls)
    done:         list[str]                  = []
    dead:         list[str]                  = []
    wset:         set[tuple[str, str]]       = set()
    _consec_fail: dict[tuple[str, str], int] = {}

    pool, buf      = _refresh_pool(pool_provider, logger, cm, buffer_size)
    _last_refresh  = time.monotonic()
    _last_progress = time.monotonic()

    while queue:
        now = time.monotonic()

        if _check_stall(now, _last_progress, queue):
            break

        pool, buf, _last_refresh = _maybe_refresh_and_refill(
            pool_provider, logger, cm, buffer_size, pool, buf, now, _last_refresh, refresh_interval_s,
        )

        batch = _build_batch(queue, wset, buf, concurrency)
        if not batch:
            sleep_s = _compute_sleep(cm, _last_refresh, refresh_interval_s)
            if sleep_s > 0:
                _sleep(sleep_s)
            buf = build_active_buffer(pool, cm, buffer_size)
            continue

        buf, _last_progress = _run_batch_cycle(
            queue, batch, content_type, content_handler, logger, cm, wset, _consec_fail, buf,
            done, dead, concurrency, _last_progress,
        )

    return done, dead, list(queue)


# FUNCTIONS

# Log + signal stall termination when no progress for STALL_TIMEOUT_S; return True if the caller should stop.
def _check_stall(now: float, last_progress: float, queue: deque) -> bool:
    if now - last_progress < STALL_TIMEOUT_S:
        return False
    print(
        f"[proxy_pool] stall: no progress for {STALL_TIMEOUT_S}s, "
        f"terminating with {len(queue)} urls unresolved → failed",
        file=sys.stderr,
    )
    return True


# Refresh the pool if due (rebuilding buf from it), then top up buf below buffer_size; return (pool, buf, last_refresh).
def _maybe_refresh_and_refill(
    pool_provider:      Callable[[], tuple[list[tuple[str, str]], list[dict]]],
    logger:             AcquireLogger,
    cm:                 PersistentCooldownManager,
    buffer_size:        int,
    pool:               list[tuple[str, str]],
    buf:                list[tuple[str, str]],
    now:                float,
    last_refresh:       float,
    refresh_interval_s: float,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], float]:
    if now - last_refresh >= refresh_interval_s:
        pool, buf    = _refresh_pool(pool_provider, logger, cm, buffer_size)
        last_refresh = time.monotonic()

    if len(buf) < buffer_size:
        buf = refill_buffer(buf, pool, cm, buffer_size)

    return pool, buf, last_refresh


# Fetch a fresh proxy list via pool_provider(), log it, rebuild the active buffer.
def _refresh_pool(
    pool_provider: Callable[[], tuple[list[tuple[str, str]], list[dict]]],
    logger:        AcquireLogger,
    cm:            PersistentCooldownManager,
    buffer_size:   int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    pool, sources = pool_provider()
    logger.record_pool_refresh(len(pool))
    for s in sources:
        logger.record_pool_source(s["url"], s["ok"], s["count"])
    buf = build_active_buffer(pool, cm, buffer_size)
    return pool, buf


# Seconds to sleep on exhaustion: min(next cooldown expiry, next refresh tick)
def _compute_sleep(
    cm: PersistentCooldownManager,
    last_refresh_mono: float,
    refresh_interval_s: float,
) -> float:
    now_mono        = time.monotonic()
    secs_to_refresh = max(0.0, (last_refresh_mono + refresh_interval_s) - now_mono)

    earliest = cm.earliest_eligible_at()
    if earliest is None:
        return secs_to_refresh

    now_utc          = datetime.now(timezone.utc)
    secs_to_eligible = max(0.0, (earliest - now_utc).total_seconds())
    return min(secs_to_refresh, secs_to_eligible)


# Build one batch: Phase 1 (wset then fresh buf → distinct URLs) + Phase 2 tail-race. Each proxy appears once.
def _build_batch(
    queue:       deque,
    wset:        set[tuple[str, str]],
    buf:         list[tuple[str, str]],
    concurrency: int,
) -> list[tuple[str, str, str]]:
    batch:            list[tuple[str, str, str]] = []
    assigned_proxies: set[tuple[str, str]]       = set()
    url_iter = iter(queue)

    _assign_batch_slots(wset, url_iter, batch, assigned_proxies, concurrency)
    _assign_batch_slots(buf, url_iter, batch, assigned_proxies, concurrency, wset=wset)

    if len(batch) < concurrency and batch:
        pending_urls = [url for _, _, url in batch]
        url_idx      = 0
        for proto, hp in list(wset) + buf:
            if len(batch) >= concurrency:
                break
            if (proto, hp) in assigned_proxies:
                continue
            batch.append((proto, hp, pending_urls[url_idx % len(pending_urls)]))
            assigned_proxies.add((proto, hp))
            url_idx += 1

    return batch


# Assign proxies to the next distinct queue URL up to concurrency, skipping already-assigned/wset proxies.
def _assign_batch_slots(
    proxies:          list[tuple[str, str]] | set[tuple[str, str]],
    url_iter,
    batch:            list[tuple[str, str, str]],
    assigned_proxies: set[tuple[str, str]],
    concurrency:      int,
    wset:             set[tuple[str, str]] | None = None,
) -> None:
    for proto, hp in proxies:
        if len(batch) >= concurrency:
            break
        if wset is not None and ((proto, hp) in assigned_proxies or (proto, hp) in wset):
            continue
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))


# Consume this batch's URLs off queue, execute it, requeue anything that failed; return (buf, last_progress).
def _run_batch_cycle(
    queue:           deque,
    batch:           list[tuple[str, str, str]],
    content_type:    str,
    content_handler: Callable[[str, bytes], None] | None,
    logger:          AcquireLogger,
    cm:              PersistentCooldownManager,
    wset:            set[tuple[str, str]],
    consec_fail:     dict[tuple[str, str], int],
    buf:             list[tuple[str, str]],
    done:            list[str],
    dead:            list[str],
    concurrency:     int,
    last_progress:   float | None,
) -> tuple[list[tuple[str, str]], float | None]:
    n_urls_consumed = len({url for _, _, url in batch})
    for _ in range(n_urls_consumed):
        queue.popleft()

    buf, batch_done, batch_failed, batch_last_progress = _execute_batch(
        batch, content_type, content_handler, logger, cm, wset, consec_fail, buf, done, dead, concurrency,
    )
    if batch_last_progress is not None:
        last_progress = batch_last_progress

    for url in batch_failed:
        if url not in batch_done:
            queue.append(url)

    return buf, last_progress


# Run one concurrent batch; mutate done/dead/wset/consec_fail in place; return (buf, batch_done, batch_failed, last_progress).
def _execute_batch(
    batch:           list[tuple[str, str, str]],
    content_type:    str,
    content_handler: Callable[[str, bytes], None] | None,
    logger:          AcquireLogger,
    cm:              PersistentCooldownManager,
    wset:            set[tuple[str, str]],
    consec_fail:     dict[tuple[str, str], int],
    buf:             list[tuple[str, str]],
    done:            list[str],
    dead:            list[str],
    concurrency:     int,
) -> tuple[list[tuple[str, str]], set[str], set[str], float | None]:
    batch_done:    set[str] = set()
    batch_failed:  set[str] = set()
    last_progress: float | None = None

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(fetch_url, p, hp, url, content_type): (p, hp, url)
            for p, hp, url in batch
        }
        for fut in as_completed(futures):
            proto, hp, url = futures[fut]
            status, content = fut.result()

            logger.record_attempt(proto, hp, url, status == "ok")

            buf, last_progress = _apply_future_outcome(
                proto, hp, url, status, content, content_handler, cm,
                wset, consec_fail, buf, done, dead, batch_done, batch_failed, last_progress,
            )

    return buf, batch_done, batch_failed, last_progress


# Apply one future's outcome (ok/dead/other) to done/dead/wset/consec_fail/batch_done/batch_failed in
# place; return (buf, last_progress) since buf may be rebound (proxy burn) and last_progress reassigned.
def _apply_future_outcome(
    proto:           str,
    hp:              str,
    url:             str,
    status:          str,
    content:         bytes,
    content_handler: Callable[[str, bytes], None] | None,
    cm:              PersistentCooldownManager,
    wset:            set[tuple[str, str]],
    consec_fail:     dict[tuple[str, str], int],
    buf:             list[tuple[str, str]],
    done:            list[str],
    dead:            list[str],
    batch_done:      set[str],
    batch_failed:    set[str],
    last_progress:   float | None,
) -> tuple[list[tuple[str, str]], float | None]:
    key = (proto, hp)

    if status == "ok":
        if url not in batch_done:
            batch_done.add(url)
            if content_handler is not None:
                content_handler(url, content)
            done.append(url)
            last_progress = time.monotonic()
        wset.add(key)
        consec_fail.pop(key, None)
    elif status == "dead":
        if url not in batch_done:
            batch_done.add(url)
            dead.append(url)
            last_progress = time.monotonic()
        wset.add(key)
        consec_fail.pop(key, None)
    else:
        batch_failed.add(url)
        fails = consec_fail.get(key, 0) + 1
        if fails >= 2:
            cm.mark_burned(proto, hp)
            wset.discard(key)
            buf = [p for p in buf if p != key]
            consec_fail.pop(key, None)
        else:
            consec_fail[key] = fails

    return buf, last_progress
