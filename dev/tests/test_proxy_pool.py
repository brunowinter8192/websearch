"""Tests for proxy_pool engine: janitor window stats (D3), retry resilience (D1),
and source-list reporting (D2). Tests are self-contained: synthetic JSONL events,
no network, no filesystem state beyond tmp_path.
"""
from src.news.engine.proxy_pool.janitor import (
    _compute_stats,
    _compute_window_stats,
    _parse_ts,
    _write_md,
)
from dev.tests._proxy_pool_fakes import _attempt, _refresh, _write_and_read_md


def _md(tmp_path, events, target=10, done=5):
    return _write_and_read_md(_compute_stats, _write_md, tmp_path, events, target, done)


# ---------------------------------------------------------------------------
# D3 — _compute_window_stats: urls_handled = distinct, fetch_attempts = total
# ---------------------------------------------------------------------------

def test_urls_handled_is_distinct_urls():
    """urls_handled counts distinct target URLs, not attempt events."""
    # 5 attempt events but only 3 distinct URLs
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        _attempt("http://p1:1", "https://target.com/a", "2026-01-01T00:00:01Z"),
        _attempt("http://p2:2", "https://target.com/a", "2026-01-01T00:00:02Z"),  # same URL, 2nd proxy
        _attempt("http://p1:1", "https://target.com/b", "2026-01-01T00:00:03Z"),
        _attempt("http://p2:2", "https://target.com/c", "2026-01-01T00:00:04Z"),
        _attempt("http://p3:3", "https://target.com/b", "2026-01-01T00:00:05Z"),  # same URL, 3rd proxy
    ]
    windows = _compute_window_stats(events, t0)
    assert len(windows) == 1
    assert windows[0]["urls_handled"] == 3   # a, b, c — distinct


def test_fetch_attempts_is_total_event_count():
    """fetch_attempts counts all attempt events (proxy × url pairs), not distinct URLs."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        _attempt("http://p1:1", "https://target.com/a", "2026-01-01T00:00:01Z"),
        _attempt("http://p2:2", "https://target.com/a", "2026-01-01T00:00:02Z"),
        _attempt("http://p1:1", "https://target.com/b", "2026-01-01T00:00:03Z"),
        _attempt("http://p2:2", "https://target.com/c", "2026-01-01T00:00:04Z"),
        _attempt("http://p3:3", "https://target.com/b", "2026-01-01T00:00:05Z"),
    ]
    windows = _compute_window_stats(events, t0)
    assert windows[0]["fetch_attempts"] == 5  # total attempt events


def test_urls_handled_ne_fetch_attempts_when_multi_proxy():
    """The two counters diverge when a URL is attempted by multiple proxies."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    # 1 distinct URL, 3 attempt events (3 proxies race the same URL)
    events = [
        _attempt("http://p1:1", "https://target.com/x", "2026-01-01T00:00:01Z", "fail"),
        _attempt("http://p2:2", "https://target.com/x", "2026-01-01T00:00:02Z", "fail"),
        _attempt("http://p3:3", "https://target.com/x", "2026-01-01T00:00:03Z", "ok"),
    ]
    windows = _compute_window_stats(events, t0)
    w = windows[0]
    assert w["urls_handled"]   == 1  # one distinct URL
    assert w["fetch_attempts"] == 3  # three proxy attempts


def test_window_stats_across_two_windows():
    """urls_handled and fetch_attempts are computed per-window independently."""
    t0 = _parse_ts("2026-01-01T00:00:00Z")
    events = [
        # window 0: 2 distinct URLs, 3 attempts
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:10:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:20:00Z"),
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:30:00Z"),
        # window 1: 1 distinct URL, 2 attempts
        _attempt("http://p1:1", "https://t.com/c", "2026-01-01T01:05:00Z"),
        _attempt("http://p2:2", "https://t.com/c", "2026-01-01T01:10:00Z"),
    ]
    windows = _compute_window_stats(events, t0)
    assert len(windows) == 2
    w0, w1 = windows[0], windows[1]
    assert w0["urls_handled"]   == 2
    assert w0["fetch_attempts"] == 3
    assert w1["urls_handled"]   == 1
    assert w1["fetch_attempts"] == 2


# ---------------------------------------------------------------------------
# D3 — job.md rendering: both columns present with correct values
# ---------------------------------------------------------------------------

def test_job_md_has_fetch_versuche_column(tmp_path):
    """job.md table header contains 'Fetch-Versuche' and 'URLs handled' as separate columns."""
    events = [
        _refresh(500, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:02:00Z"),
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:03:00Z"),
    ]
    md = _md(tmp_path, events)
    assert "Fetch-Versuche" in md
    assert "URLs handled"   in md


def test_job_md_urls_handled_and_fetch_attempts_values(tmp_path):
    """job.md row values: urls_handled = 2 (distinct), fetch_attempts = 3 (total)."""
    events = [
        _refresh(500, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
        _attempt("http://p2:2", "https://t.com/a", "2026-01-01T00:02:00Z"),  # same URL
        _attempt("http://p1:1", "https://t.com/b", "2026-01-01T00:03:00Z"),
    ]
    md = _md(tmp_path, events)
    # Window 0 row: | 0 | probiert | erfolgreich | 2 | 3 | 500 |
    assert "| 0 |" in md
    lines = [l for l in md.splitlines() if l.startswith("| 0 |")]
    assert lines, "Window 0 row not found in job.md"
    row = lines[0]
    cols = [c.strip() for c in row.split("|")]
    # cols[0]='', cols[1]='0', cols[2]=probiert, cols[3]=erfolgreich,
    # cols[4]=urls_handled, cols[5]=fetch_attempts, cols[6]=pool_size
    assert cols[4] == "2", f"urls_handled wrong: {cols[4]}"
    assert cols[5] == "3", f"fetch_attempts wrong: {cols[5]}"
