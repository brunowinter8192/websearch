# INFRASTRUCTURE
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import src.search.browser_lock as browser_lock


# FUNCTIONS

def test_acquire_returns_immediately_when_free(tmp_path):
    lock_path = tmp_path / "session.lock"
    handle = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    assert lock_path.exists()
    assert lock_path.with_suffix(".json").exists()
    handle.release()


def test_release_removes_sidecar(tmp_path):
    lock_path = tmp_path / "session.lock"
    handle = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    sidecar = lock_path.with_suffix(".json")
    assert sidecar.exists()
    handle.release()
    assert not sidecar.exists()


def test_acquire_blocks_until_release(tmp_path):
    lock_path = tmp_path / "session.lock"
    holder = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    released_at = {}
    about_to_release = threading.Event()

    def hold_then_release():
        about_to_release.wait(timeout=5)
        released_at["t"] = time.monotonic()
        holder.release()

    t = threading.Thread(target=hold_then_release)
    t.start()
    about_to_release.set()
    second = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    acquired_at = time.monotonic()
    t.join()

    assert acquired_at >= released_at["t"]
    second.release()


def test_stale_lock_is_broken_and_on_stale_invoked(tmp_path):
    lock_path = tmp_path / "session.lock"
    sidecar = lock_path.with_suffix(".json")
    stuck_holder = browser_lock.acquire(lock_path, hard_budget_s=9999.0)
    try:
        old = datetime.now(timezone.utc) - timedelta(seconds=120)
        sidecar.write_text(
            '{"pid": 999999, "started_at": "%s"}' % old.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )
        stale_calls = []
        handle = browser_lock.acquire(lock_path, hard_budget_s=1.0, on_stale=lambda: stale_calls.append(1))
        assert stale_calls == [1]
        handle.release()
    finally:
        stuck_holder.release()


def test_stale_takeover_not_triggered_under_budget(tmp_path, monkeypatch):
    waiter_polled = threading.Event()
    real_sleep = time.sleep

    def signalling_sleep(seconds):
        waiter_polled.set()
        real_sleep(0.01)

    monkeypatch.setattr(browser_lock, "time", type("T", (), {"sleep": staticmethod(signalling_sleep)}))
    lock_path = tmp_path / "session.lock"
    holder = browser_lock.acquire(lock_path, hard_budget_s=60.0)
    stale_calls = []

    def try_acquire():
        h = browser_lock.acquire(lock_path, hard_budget_s=60.0, on_stale=lambda: stale_calls.append(1))
        h.release()

    t = threading.Thread(target=try_acquire)
    t.start()
    assert waiter_polled.wait(timeout=5)
    holder.release()
    t.join(timeout=5)
    assert stale_calls == []


def test_sidecar_age_s_missing_file_returns_none(tmp_path):
    assert browser_lock._sidecar_age_s(tmp_path / "nope.json") is None
