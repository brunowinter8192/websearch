from unittest.mock import MagicMock, patch

import src.news.engine.proxy_pool.loop as loop_module
from src.news.engine.proxy_pool.loop import run_loop
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager


def _run_loop_with_mocked_time(pool_a, pool_b, sources, target_urls, concurrency, buffer_size,
                               refresh_interval_s, mono_seq):
    pool_provider = MagicMock(side_effect=[
        (pool_a, sources),  # call 1 — startup
        (pool_b, sources),  # call 2 — refresh
    ])
    mock_fetch  = MagicMock(return_value=("ok", b"content"))
    mock_logger = MagicMock(spec=AcquireLogger)
    cm          = PersistentCooldownManager()

    with (
        patch("src.news.engine.proxy_pool.loop.fetch_url", mock_fetch),
        patch("src.news.engine.proxy_pool.loop.time") as mock_time,
        patch.object(loop_module, "_sleep"),
    ):
        mock_time.monotonic.side_effect = iter(mono_seq)
        done, dead, gap = run_loop(
            pool_provider      = pool_provider,
            target_urls        = target_urls,
            content_type       = "html",
            logger             = mock_logger,
            cm                 = cm,
            concurrency        = concurrency,
            buffer_size        = buffer_size,
            refresh_interval_s = refresh_interval_s,
        )
    return done, dead, gap, pool_provider, mock_fetch, mock_logger


def _swap_preserves_state_scenario():
    POOL_A  = [("http", "A1:80"), ("http", "A2:80")]
    POOL_B  = [("http", "B1:80"), ("http", "B2:80")]
    SOURCES = [{"url": "https://src.example", "ok": True, "count": 2}]
    target_urls = [
        "https://target.com/1",
        "https://target.com/2",
        "https://target.com/3",
    ]
    # time.monotonic sequence — 9 real calls (corrected 2026-08-20; the previous 5-value sequence
    # undercounted by omitting the startup _last_progress call and the per-resolution _last_progress
    # update inside _execute_batch, causing the refresh to fire before batch 1 ever ran — see this
    # milestone's process-docs entry for the traced call-by-call evidence):
    #   #1 _last_refresh=0.0 (startup)  #2 _last_progress=0.0 (startup)
    #   #3 now(iter1)=0.0 → 0-0=0<10 → no refresh
    #   [batch 1: A1→url1 ok, A1 enters wset]  #4 _last_progress=0.0 (post-batch1 update)
    #   #5 now(iter2)=15.0 → 15-0=15≥10 → REFRESH fires  #6 _last_refresh=15.0 (post-refresh)
    #   [batch 2: A1(wset)→url2 ok, post-swap]  #7 _last_progress=15.0 (post-batch2 update)
    #   #8 now(iter3)=15.0 → 15-15=0<10 → no refresh
    #   [batch 3: →url3 ok; queue empty → return]  #9 _last_progress=15.0 (post-batch3 update)
    mono_seq = [0.0, 0.0, 0.0, 0.0, 15.0, 15.0, 15.0, 15.0, 15.0] + [15.0] * 10
    return POOL_A, POOL_B, SOURCES, target_urls, mono_seq


def _fresh_candidates_scenario():
    POOL_A  = [("http", "A1:80")]                          # single proxy
    POOL_B  = [("http", "B1:80"), ("http", "B2:80")]       # two fresh proxies
    SOURCES = [{"url": "https://src.example", "ok": True, "count": 1}]
    target_urls = [
        "https://target.com/1",
        "https://target.com/2",
        "https://target.com/3",
        "https://target.com/4",
    ]
    # time.monotonic sequence — 9 real calls (corrected 2026-08-20, same undercounting fix as
    # test_run_loop_refresh_swaps_pool_and_preserves_state above — see this milestone's process-docs
    # entry for the traced call-by-call evidence):
    #   #1 _last_refresh=0.0 (startup)  #2 _last_progress=0.0 (startup)
    #   #3 now(iter1)=0.0 → no refresh
    #   [batch 1: only A1 in pool → A1→url1 ok; wset={A1}]  #4 _last_progress=0.0 (post-batch1)
    #   #5 now(iter2)=15.0 → REFRESH  #6 _last_refresh=15.0 (post-refresh)
    #   [batch 2: concurrency=3; A1(wset)→url2, B1(buf)→url3, B2(buf)→url4; all ok —
    #    3 futures each call _last_progress once]  #7,#8,#9 _last_progress=15.0 (post-batch2 x3)
    #   queue empty after n_urls_consumed=3 → return
    mono_seq = [0.0, 0.0, 0.0, 0.0, 15.0, 15.0, 15.0, 15.0, 15.0] + [15.0] * 10
    return POOL_A, POOL_B, SOURCES, target_urls, mono_seq


# ---------------------------------------------------------------------------
# Integration — run_loop over a 60-min refresh boundary
# ---------------------------------------------------------------------------

def test_run_loop_refresh_swaps_pool_and_preserves_state():
    """run_loop calls pool_provider twice, preserves queue/done/wset across the swap.

    Proves:
    - pool_provider called exactly 2× (startup + one refresh).
    - All 3 target URLs reach done — none dropped at the swap boundary.
    - Pool A proxy A1:80 enters wset pre-refresh and is still dispatched for url2
      post-refresh (wset is never touched by _refresh_pool — only pool/buf are).
    - Logger receives 2 record_pool_refresh events with correct pool sizes.
    """
    POOL_A, POOL_B, SOURCES, target_urls, mono_seq = _swap_preserves_state_scenario()

    done, dead, gap, pool_provider, mock_fetch, mock_logger = _run_loop_with_mocked_time(
        POOL_A, POOL_B, SOURCES, target_urls, concurrency=1, buffer_size=2,
        refresh_interval_s=10.0, mono_seq=mono_seq,
    )

    # 1. Pool swap happened exactly once
    assert pool_provider.call_count == 2, (
        f"Expected 2 pool_provider calls (startup + refresh), got {pool_provider.call_count}"
    )

    # 2. State continuity: all URLs processed, none dropped
    assert set(done) == set(target_urls), f"URLs lost across swap: {set(target_urls) - set(done)}"
    assert dead == []
    assert gap  == []

    # 3. Logger received both pool_refresh events with correct sizes
    assert mock_logger.record_pool_refresh.call_count == 2
    sizes = [c.args[0] for c in mock_logger.record_pool_refresh.call_args_list]
    assert sizes == [len(POOL_A), len(POOL_B)]

    # 4. wset survival: Pool A proxy A1:80 dispatched for url2 (the first URL after the refresh)
    #    fetch_url call order with concurrency=1: [url1, url2, url3]
    assert mock_fetch.call_count == 3
    post_swap_call = mock_fetch.call_args_list[1]   # url2 batch (iter 2, post-refresh)
    assert post_swap_call.args[1] == "A1:80", (
        f"wset survival failed: expected Pool-A proxy 'A1:80' to be dispatched "
        f"post-refresh, got {post_swap_call.args[1]!r}"
    )
    assert post_swap_call.args[2] == target_urls[1]


def test_run_loop_refresh_fresh_candidates_from_new_pool():
    """After swap, Pool B proxies enter via rebuilt buf and are dispatched alongside wset proxy.

    Proves:
    - With Pool A having only 1 proxy (A1:80) and concurrency=3, iter 1 builds
      wset={A1:80} via a single-proxy batch.
    - On the refresh, buf is rebuilt from Pool B=[B1:80, B2:80].
    - Iter 2 batch: A1:80 (wset) + B1:80 + B2:80 (buf) race 3 URLs in one batch —
      the new pool's proxies are immediately active alongside the surviving wset proxy.
    - All 4 URLs reach done; gap empty.
    """
    POOL_A, POOL_B, SOURCES, target_urls, mono_seq = _fresh_candidates_scenario()

    done, dead, gap, pool_provider, mock_fetch, mock_logger = _run_loop_with_mocked_time(
        POOL_A, POOL_B, SOURCES, target_urls, concurrency=3, buffer_size=2,
        refresh_interval_s=10.0, mono_seq=mono_seq,
    )

    # 1. Swap happened exactly once
    assert pool_provider.call_count == 2

    # 2. All URLs processed, none dropped
    assert set(done) == set(target_urls), f"URLs lost: {set(target_urls) - set(done)}"
    assert dead == []
    assert gap  == []

    # 3. Pool B proxies dispatched post-refresh (via rebuilt buf)
    dispatched_hps  = {c.args[1] for c in mock_fetch.call_args_list}
    pool_b_hps      = {"B1:80", "B2:80"}
    assert dispatched_hps & pool_b_hps, (
        f"No Pool B proxy dispatched after refresh — "
        f"buf rebuild not working. Dispatched: {dispatched_hps}"
    )

    # 4. wset proxy also present post-refresh (A1:80 from Pool A survived in wset)
    assert "A1:80" in dispatched_hps, (
        f"Pool A proxy A1:80 missing from dispatched set — wset cleared unexpectedly"
    )
