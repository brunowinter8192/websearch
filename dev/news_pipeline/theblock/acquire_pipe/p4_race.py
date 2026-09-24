# INFRASTRUCTURE

import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p5_logger import AcquireLogger
from p6_buffer import DEFAULT_CONCURRENCY


@dataclass
class RaceState:
    candidates:  list[tuple[str, str]]
    proxy_idx:   int
    proxy_lock:  threading.Lock
    url_list:    list[str]
    url_idx:     int
    done_set:    set[str]
    done:        list[str]
    lock:        threading.Lock
    total:       int


# ORCHESTRATOR

def run_race(
    pool:            list[tuple[str, str]],
    target_urls:     list[str],
    content_type:    str,
    logger:          AcquireLogger,
    content_handler: Callable[[str, bytes], None] | None = None,
    concurrency:     int = DEFAULT_CONCURRENCY,
) -> tuple[list[str], list[str]]:
    candidates  = pool[:]
    random.shuffle(candidates)

    _url_list = list(target_urls)
    state = RaceState(
        candidates=candidates, proxy_idx=0, proxy_lock=threading.Lock(),
        url_list=_url_list, url_idx=0, done_set=set(), done=[],
        lock=threading.Lock(), total=len(_url_list),
    )

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(_worker, state, logger, content_type, content_handler) for _ in range(concurrency)]
        for f in as_completed(futures):
            f.result()

    gap = [u for u in _url_list if u not in state.done_set]
    return state.done, gap


# FUNCTIONS

def _worker(
    state:           RaceState,
    logger:          AcquireLogger,
    content_type:    str,
    content_handler: Callable[[str, bytes], None] | None,
) -> None:
    while True:
        url = _next_url(state)
        if url is None:
            return
        proxy = _next_proxy(state)
        if proxy is None:
            return
        proto, hp = proxy
        status, content = fetch_url(proto, hp, url, content_type)
        logger.record_attempt(proto, hp, url, status == "ok")
        if status == "ok":
            _mark_done(state, url, content, content_handler)


def _next_url(state: RaceState) -> str | None:
    with state.lock:
        n = len(state.url_list)
        for _ in range(n):
            url = state.url_list[state.url_idx % n]
            state.url_idx += 1
            if url not in state.done_set:
                return url
        return None


def _next_proxy(state: RaceState) -> tuple[str, str] | None:
    with state.proxy_lock:
        if state.proxy_idx >= len(state.candidates):
            return None
        p = state.candidates[state.proxy_idx]
        state.proxy_idx += 1
        return p


def _mark_done(
    state:           RaceState,
    url:             str,
    content:         bytes,
    content_handler: Callable[[str, bytes], None] | None,
) -> None:
    newly  = False
    n_done = 0
    name   = url.split("/")[-1]
    with state.lock:
        if url not in state.done_set:
            state.done_set.add(url)
            state.done.append(url)
            newly  = True
            n_done = len(state.done_set)
    if newly:
        print(f"[race] {n_done}/{state.total} done: {name}")
        if content_handler is not None:
            content_handler(url, content)
