from unittest.mock import MagicMock, call, patch

import httpx
import pytest

import src.news.engine.proxy_pool.pool_retry as pool_retry


# ---------------------------------------------------------------------------
# D1 — pool_retry.fetch_with_retry
# ---------------------------------------------------------------------------

def test_fetch_with_retry_recovers_after_transient_failure():
    """fetch_with_retry returns the result when fn() eventually succeeds before attempt 5."""
    call_count = [0]

    def flaky():
        call_count[0] += 1
        if call_count[0] < 3:
            raise httpx.ConnectError("transient")
        return "recovered"

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        result = pool_retry.fetch_with_retry(flaky)

    assert result == "recovered"
    assert call_count[0] == 3
    # sleep called between attempt 1→2 (1s) and attempt 2→3 (2s)
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list == [call(1), call(2)]


def test_fetch_with_retry_reraises_after_all_attempts():
    """fetch_with_retry re-raises the last exception after 5 failed attempts."""
    call_count = [0]

    def always_fail():
        call_count[0] += 1
        raise httpx.ConnectError("persistent")

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        with pytest.raises(httpx.ConnectError, match="persistent"):
            pool_retry.fetch_with_retry(always_fail)

    assert call_count[0] == 5
    assert mock_sleep.call_count == 4  # slept between each of the 5 attempts


def test_fetch_with_retry_no_sleep_on_first_attempt():
    """fetch_with_retry does not sleep before the very first attempt."""
    def succeed_immediately():
        return 42

    with patch.object(pool_retry, "_sleep") as mock_sleep:
        result = pool_retry.fetch_with_retry(succeed_immediately)

    assert result == 42
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# D1 — load_backfill_pool: per-source isolation (continue on failure, no raise)
# ---------------------------------------------------------------------------

def test_load_backfill_pool_continues_when_monosans_fails():
    """If monosans exhausts all retries, pool contains entries from other sources; no exception raised."""
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

    def mock_get(url, timeout):
        if "monosans" in url:
            raise httpx.ConnectError("test blip")
        resp = MagicMock()
        resp.text = "1.2.3.4:1080\n5.6.7.8:3128\n"
        resp.raise_for_status = lambda: None
        return resp

    with patch("httpx.get", side_effect=mock_get), patch.object(pool_retry, "_sleep"):
        pool, sources = load_backfill_pool()

    monosans_src = next(s for s in sources if "monosans" in s["url"])
    assert monosans_src["ok"] is False
    assert monosans_src["count"] == 0

    # Other sources contributed entries → pool is non-empty
    assert len(pool) > 0
    ok_sources = [s for s in sources if s["ok"]]
    assert len(ok_sources) > 0


def test_load_backfill_pool_source_count_on_success():
    """A successful source records count == number of parsed proxy entries."""
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool, THESPEEDX_SOURCES

    resp = MagicMock()
    # 3 valid lines per request → each bare_txt source gets count=3
    resp.text = "1.1.1.1:80\n2.2.2.2:80\n3.3.3.3:80\n"
    resp.json.return_value = [
        {"protocol": "http", "host": "4.4.4.4", "port": 80},
    ]
    resp.raise_for_status = lambda: None

    with patch("httpx.get", return_value=resp), patch.object(pool_retry, "_sleep"):
        _, sources = load_backfill_pool()

    # Check one of the TheSpeedX bare-txt sources
    thespeedx_http_url = THESPEEDX_SOURCES[0][1]
    src = next(s for s in sources if s["url"] == thespeedx_http_url)
    assert src["ok"] is True
    assert src["count"] == 3
