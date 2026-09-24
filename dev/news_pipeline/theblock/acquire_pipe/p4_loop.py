# INFRASTRUCTURE

import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p2_cooldown import PersistentCooldownManager
from p5_logger import AcquireLogger
from p6_buffer import build_active_buffer, refill_buffer, BUFFER_SIZE, DEFAULT_CONCURRENCY

_sleep             = time.sleep
REFRESH_INTERVAL_S = 3600


@dataclass
class LoopState:
    queue:        deque
    done:         list[str]
    dead:         list[str]
    wset:         set[tuple[str, str]]
    consec_fail:  dict[tuple[str, str], int]
    pool:         list[tuple[str, str]]
    buf:          list[tuple[str, str]]
    last_refresh: float


# ORCHESTRATOR

def run_loop(
    pool_provider: Callable[[], list[tuple[str, str]]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    concurrency: int = DEFAULT_CONCURRENCY,
    buffer_size: int = BUFFER_SIZE,
    content_handler: Callable[[str, bytes], None] | None = None,
    refresh_interval_s: float = REFRESH_INTERVAL_S,
) -> tuple[list[str], list[str], list[str]]:
    state = _init_state(pool_provider, target_urls, logger, cm, buffer_size)

    while state.queue:
        _run_iteration(
            state, pool_provider, content_type, concurrency, logger, cm,
            buffer_size, content_handler, refresh_interval_s,
        )

    return state.done, state.dead, list(state.queue)


# FUNCTIONS

def _init_state(
    pool_provider: Callable[[], list[tuple[str, str]]],
    target_urls: list[str],
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    buffer_size: int,
) -> LoopState:
    pool_22k, buf, last_refresh = _reload_pool(pool_provider, logger, cm, buffer_size)
    return LoopState(
        queue=deque(target_urls), done=[], dead=[], wset=set(), consec_fail={},
        pool=pool_22k, buf=buf, last_refresh=last_refresh,
    )


def _run_iteration(
    state:              LoopState,
    pool_provider:      Callable[[], list[tuple[str, str]]],
    content_type:       str,
    concurrency:        int,
    logger:             AcquireLogger,
    cm:                 PersistentCooldownManager,
    buffer_size:        int,
    content_handler:    Callable[[str, bytes], None] | None,
    refresh_interval_s: float,
) -> None:
    now = time.monotonic()

    if now - state.last_refresh >= refresh_interval_s:
        state.pool, state.buf, state.last_refresh = _reload_pool(pool_provider, logger, cm, buffer_size)

    if len(state.buf) < buffer_size:
        state.buf = refill_buffer(state.buf, state.pool, cm, buffer_size)

    batch = _build_batch(state.queue, state.wset, state.buf, concurrency)
    if not batch:
        _sleep_until_eligible(cm, state.last_refresh, refresh_interval_s)
        state.buf = build_active_buffer(state.pool, cm, buffer_size)
        return

    n_urls_consumed = len({url for _, _, url in batch})
    for _ in range(n_urls_consumed):
        state.queue.popleft()

    state.buf = _run_batch(
        batch, state.buf, state.queue, state.done, state.dead, state.wset, state.consec_fail,
        content_type, concurrency, logger, cm, content_handler,
    )


def _reload_pool(
    pool_provider: Callable[[], list[tuple[str, str]]],
    logger: AcquireLogger,
    cm: PersistentCooldownManager,
    buffer_size: int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], float]:
    pool_22k = pool_provider()
    logger.record_pool_refresh(len(pool_22k))
    buf      = build_active_buffer(pool_22k, cm, buffer_size)
    return pool_22k, buf, time.monotonic()


def _sleep_until_eligible(
    cm: PersistentCooldownManager,
    last_refresh_mono: float,
    refresh_interval_s: float,
) -> None:
    sleep_s = _compute_sleep(cm, last_refresh_mono, refresh_interval_s)
    if sleep_s > 0:
        _sleep(sleep_s)


def _run_batch(
    batch:           list[tuple[str, str, str]],
    buf:             list[tuple[str, str]],
    queue:           deque,
    done:            list[str],
    dead:            list[str],
    wset:            set[tuple[str, str]],
    _consec_fail:    dict[tuple[str, str], int],
    content_type:    str,
    concurrency:     int,
    logger:          AcquireLogger,
    cm:              PersistentCooldownManager,
    content_handler: Callable[[str, bytes], None] | None,
) -> list[tuple[str, str]]:
    batch_done:   set[str] = set()
    batch_failed: set[str] = set()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(fetch_url, p, hp, url, content_type): (p, hp, url)
            for p, hp, url in batch
        }
        for fut in as_completed(futures):
            proto, hp, url = futures[fut]
            status, content = fut.result()
            key             = (proto, hp)

            logger.record_attempt(proto, hp, url, status == "ok")

            if status == "ok":
                _record_ok(url, key, content, batch_done, content_handler, done, wset, _consec_fail)
            elif status == "dead":
                _record_dead(url, key, batch_done, dead, wset, _consec_fail)
            else:
                batch_failed.add(url)
                buf = _record_fail(proto, hp, key, cm, wset, buf, _consec_fail)

    for url in batch_failed:
        if url not in batch_done:
            queue.append(url)

    return buf


def _record_ok(
    url:             str,
    key:             tuple[str, str],
    content:         bytes,
    batch_done:      set[str],
    content_handler: Callable[[str, bytes], None] | None,
    done:            list[str],
    wset:            set[tuple[str, str]],
    _consec_fail:    dict[tuple[str, str], int],
) -> None:
    if url not in batch_done:
        batch_done.add(url)
        if content_handler is not None:
            content_handler(url, content)
        done.append(url)
    wset.add(key)
    _consec_fail.pop(key, None)


def _record_dead(
    url:          str,
    key:          tuple[str, str],
    batch_done:   set[str],
    dead:         list[str],
    wset:         set[tuple[str, str]],
    _consec_fail: dict[tuple[str, str], int],
) -> None:
    if url not in batch_done:
        batch_done.add(url)
        dead.append(url)
    wset.add(key)
    _consec_fail.pop(key, None)


def _record_fail(
    proto:        str,
    hp:           str,
    key:          tuple[str, str],
    cm:           PersistentCooldownManager,
    wset:         set[tuple[str, str]],
    buf:          list[tuple[str, str]],
    _consec_fail: dict[tuple[str, str], int],
) -> list[tuple[str, str]]:
    fails = _consec_fail.get(key, 0) + 1
    if fails >= 2:
        cm.mark_burned(proto, hp)
        wset.discard(key)
        buf = [p for p in buf if p != key]
        _consec_fail.pop(key, None)
    else:
        _consec_fail[key] = fails
    return buf


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


def _build_batch(
    queue:       deque,
    wset:        set[tuple[str, str]],
    buf:         list[tuple[str, str]],
    concurrency: int,
) -> list[tuple[str, str, str]]:
    batch, assigned_proxies = _assign_normal(queue, wset, buf, concurrency)

    _add_tail_racers(batch, assigned_proxies, wset, buf, concurrency)

    return batch


def _assign_normal(
    queue:       deque,
    wset:        set[tuple[str, str]],
    buf:         list[tuple[str, str]],
    concurrency: int,
) -> tuple[list[tuple[str, str, str]], set[tuple[str, str]]]:
    batch:            list[tuple[str, str, str]] = []
    assigned_proxies: set[tuple[str, str]]       = set()
    url_iter = iter(queue)

    for proto, hp in wset:
        if len(batch) >= concurrency:
            break
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    for proto, hp in buf:
        if len(batch) >= concurrency:
            break
        if (proto, hp) in assigned_proxies or (proto, hp) in wset:
            continue
        url = next(url_iter, None)
        if url is None:
            break
        batch.append((proto, hp, url))
        assigned_proxies.add((proto, hp))

    return batch, assigned_proxies


def _add_tail_racers(
    batch:            list[tuple[str, str, str]],
    assigned_proxies: set[tuple[str, str]],
    wset:             set[tuple[str, str]],
    buf:              list[tuple[str, str]],
    concurrency:      int,
) -> None:
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
