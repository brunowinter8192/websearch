# INFRASTRUCTURE
from unittest.mock import MagicMock, patch

import src.news.engine.proxy_pool.loop as loop_module
from src.news.engine.proxy_pool.loop import run_loop
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager


# FUNCTIONS

def test_run_loop_refresh_swaps_pool_and_preserves_state():
    POOL_A, POOL_B, SOURCES, target_urls, mono_seq = _swap_preserves_state_scenario()

    done, dead, gap, pool_provider, mock_fetch, mock_logger = _run_loop_with_mocked_time(
        POOL_A, POOL_B, SOURCES, target_urls, concurrency=1, buffer_size=2,
        refresh_interval_s=10.0, mono_seq=mono_seq,
    )

    assert pool_provider.call_count == 2, (
        f"Expected 2 pool_provider calls (startup + refresh), got {pool_provider.call_count}"
    )

    assert set(done) == set(target_urls), f"URLs lost across swap: {set(target_urls) - set(done)}"
    assert dead == []
    assert gap  == []

    assert mock_logger.record_pool_refresh.call_count == 2
    sizes = [c.args[0] for c in mock_logger.record_pool_refresh.call_args_list]
    assert sizes == [len(POOL_A), len(POOL_B)]

    assert mock_fetch.call_count == 3
    post_swap_call = mock_fetch.call_args_list[1]
    assert post_swap_call.args[1] == "A1:80", (
        f"wset survival failed: expected Pool-A proxy 'A1:80' to be dispatched "
        f"post-refresh, got {post_swap_call.args[1]!r}"
    )
    assert post_swap_call.args[2] == target_urls[1]


def test_run_loop_refresh_fresh_candidates_from_new_pool():
    POOL_A, POOL_B, SOURCES, target_urls, mono_seq = _fresh_candidates_scenario()

    done, dead, gap, pool_provider, mock_fetch, mock_logger = _run_loop_with_mocked_time(
        POOL_A, POOL_B, SOURCES, target_urls, concurrency=3, buffer_size=2,
        refresh_interval_s=10.0, mono_seq=mono_seq,
    )

    assert pool_provider.call_count == 2

    assert set(done) == set(target_urls), f"URLs lost: {set(target_urls) - set(done)}"
    assert dead == []
    assert gap  == []

    dispatched_hps  = {c.args[1] for c in mock_fetch.call_args_list}
    pool_b_hps      = {"B1:80", "B2:80"}
    assert dispatched_hps & pool_b_hps, (
        f"No Pool B proxy dispatched after refresh — "
        f"buf rebuild not working. Dispatched: {dispatched_hps}"
    )

    assert "A1:80" in dispatched_hps, (
        f"Pool A proxy A1:80 missing from dispatched set — wset cleared unexpectedly"
    )


def _swap_preserves_state_scenario():
    POOL_A  = [("http", "A1:80"), ("http", "A2:80")]
    POOL_B  = [("http", "B1:80"), ("http", "B2:80")]
    SOURCES = [{"url": "https://src.example", "ok": True, "count": 2}]
    target_urls = [
        "https://target.com/1",
        "https://target.com/2",
        "https://target.com/3",
    ]
    mono_seq = [0.0, 0.0, 0.0, 0.0, 15.0, 15.0, 15.0, 15.0, 15.0] + [15.0] * 10
    return POOL_A, POOL_B, SOURCES, target_urls, mono_seq


def _run_loop_with_mocked_time(pool_a, pool_b, sources, target_urls, concurrency, buffer_size,
                               refresh_interval_s, mono_seq):
    pool_provider = MagicMock(side_effect=[
        (pool_a, sources),
        (pool_b, sources),
    ])
    mock_fetch  = MagicMock(return_value=("ok", b"content", None))
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


def _fresh_candidates_scenario():
    POOL_A  = [("http", "A1:80")]
    POOL_B  = [("http", "B1:80"), ("http", "B2:80")]
    SOURCES = [{"url": "https://src.example", "ok": True, "count": 1}]
    target_urls = [
        "https://target.com/1",
        "https://target.com/2",
        "https://target.com/3",
        "https://target.com/4",
    ]
    mono_seq = [0.0, 0.0, 0.0, 0.0, 15.0, 15.0, 15.0, 15.0, 15.0] + [15.0] * 10
    return POOL_A, POOL_B, SOURCES, target_urls, mono_seq
