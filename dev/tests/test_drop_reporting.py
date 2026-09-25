import json
import logging
import os
from types import SimpleNamespace

import pytest

from src.crawler import pipe_scraper_acquisition, seed_feeders_navtree
from src.news.engine.proxy_pool import box_lock
from src.news.platforms.theblock import cleanup as theblock_cleanup
from src.scraper import camoufox_scrape, chromium_scrape


class _FramelessRequest:
    resource_type = "document"

    @property
    def frame(self):
        raise RuntimeError("Frame for this navigation request is not available")


def _frameless_response():
    return SimpleNamespace(request=_FramelessRequest(), url="https://x.test/sw", status=200)


class _FakePage:
    main_frame = object()

    def __init__(self):
        self.handlers = {}

    def on(self, event, handler):
        self.handlers[event] = handler


def test_camoufox_listener_logs_dropped_frameless_response(caplog):
    chain = []
    listener = camoufox_scrape._make_document_status_listener(_FakePage(), chain)
    with caplog.at_level(logging.DEBUG, logger="src.scraper.camoufox_scrape"):
        listener(_frameless_response())
    assert chain == []
    assert any("request.frame unavailable" in m and "https://x.test/sw" in m for m in caplog.messages)


def test_chromium_listener_logs_dropped_frameless_response(caplog):
    chain = []
    page = _FakePage()
    chromium_scrape._make_document_status_listener(chain)(page)
    with caplog.at_level(logging.DEBUG, logger="src.scraper.chromium_scrape"):
        page.handlers["response"](_frameless_response())
    assert chain == []
    assert any("request.frame unavailable" in m and "https://x.test/sw" in m for m in caplog.messages)


def test_listener_still_records_main_frame_document_status():
    page = _FakePage()
    request = SimpleNamespace(resource_type="document", frame=page.main_frame)
    chain = []
    camoufox_scrape._make_document_status_listener(page, chain)(SimpleNamespace(request=request, url="u", status=301))
    assert chain == [301]


@pytest.fixture
def lock_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(box_lock, "LOCK_DIR", tmp_path)
    return tmp_path


def test_cleanup_stale_raises_on_unreadable_sidecar(lock_dir):
    sidecar = lock_dir / "proxy_pool.lock"
    sidecar.write_text("not json{")
    with pytest.raises(json.JSONDecodeError):
        box_lock.cleanup_stale(sidecar)
    assert sidecar.exists()


def test_cleanup_stale_removes_sidecar_of_dead_pid(lock_dir):
    sidecar = lock_dir / "proxy_pool.lock"
    sidecar.write_text(json.dumps({"pid": 2 ** 22 + 12345}))
    box_lock.cleanup_stale(sidecar)
    assert not sidecar.exists()


def test_cleanup_stale_logs_when_pid_owned_by_other_user(lock_dir, monkeypatch, caplog):
    sidecar = lock_dir / "proxy_pool.lock"
    sidecar.write_text(json.dumps({"pid": 1}))

    def deny(pid, sig):
        raise PermissionError

    monkeypatch.setattr(os, "kill", deny)
    with caplog.at_level(logging.WARNING, logger="src.news.engine.proxy_pool.box_lock"):
        box_lock.cleanup_stale(sidecar)
    assert sidecar.exists()
    assert any("owned by another user" in m for m in caplog.messages)


def test_busy_message_raises_on_unreadable_sidecar(lock_dir):
    sidecar = lock_dir / "proxy_pool.lock"
    sidecar.write_text("not json{")
    with pytest.raises(json.JSONDecodeError):
        box_lock._busy_message(sidecar)


def test_busy_message_reports_holder(lock_dir):
    sidecar = lock_dir / "proxy_pool.lock"
    sidecar.write_text(json.dumps({"pid": 7, "job": "j", "target": "t"}))
    assert box_lock._busy_message(sidecar) == "proxy_pool already running: pid=7, job='j', target='t'"


def test_onward_link_identity_logs_malformed_url(caplog):
    with caplog.at_level(logging.WARNING, logger="src.crawler.pipe_scraper_acquisition"):
        assert pipe_scraper_acquisition.onward_link_identity("http://[bad") is None
    assert any("malformed URL" in m for m in caplog.messages)


def test_onward_link_identity_hostless_stays_silent(caplog):
    with caplog.at_level(logging.DEBUG, logger="src.crawler.pipe_scraper_acquisition"):
        assert pipe_scraper_acquisition.onward_link_identity("mailto:a@b.test") is None
    assert caplog.messages == []


def _push(text):
    return "self.__next_f.push([1," + json.dumps(text) + "])"


def test_rsc_stream_counts_non_json_rows(caplog):
    stream = '1:{"a":1}\n2:T5,hello\n3:{"b":2}'
    html = f"<script>{_push(stream)}</script>"
    with caplog.at_level(logging.DEBUG, logger="src.crawler.seed_feeders_navtree"):
        payloads = seed_feeders_navtree._extract_rsc_stream_payloads(html)
    assert payloads == [{"a": 1}, {"b": 2}]
    assert any("1 of 3 rows" in m for m in caplog.messages)


def test_theblock_malformed_json_ld_is_reported(capsys):
    article = {"@type": "NewsArticle", "articleBody": "<p>Body</p>", "datePublished": "2024-01-01"}
    html = (
        '<script type="application/ld+json">{broken</script>'
        f'<script type="application/ld+json">{json.dumps(article)}</script>'
    )
    found = theblock_cleanup._find_news_article(html, "https://theblock.test/a")
    assert found == article
    err = capsys.readouterr().err
    assert "malformed JSON-LD block skipped" in err and "https://theblock.test/a" in err
