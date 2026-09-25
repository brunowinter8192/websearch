# INFRASTRUCTURE
from types import SimpleNamespace

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError, Timeout

import src.news.engine.proxy_pool.fetch as fetch_mod


# FUNCTIONS

@pytest.mark.parametrize("exc,name", [(Timeout("t"), "Timeout"), (CurlConnectionError("c"), "ConnectionError")])
def test_transport_errors_become_fail_with_class_name(monkeypatch, exc, name):
    _patch(monkeypatch, exc=exc)
    assert fetch_mod.fetch_url("http", "h:1", "https://x.test", "xml") == ("fail", b"", name)


def test_non_transport_exception_propagates(monkeypatch):
    _patch(monkeypatch, exc=TypeError("programming error"))
    with pytest.raises(TypeError):
        fetch_mod.fetch_url("http", "h:1", "https://x.test", "xml")


def test_ok_dead_and_fail_statuses_carry_reasons(monkeypatch):
    _patch(monkeypatch, response=_resp(200, b"<?xml version='1.0'?><urlset/>"))
    assert fetch_mod.fetch_url("http", "h:1", "u", "xml")[::2] == ("ok", None)
    _patch(monkeypatch, response=_resp(404))
    assert fetch_mod.fetch_url("http", "h:1", "u", "xml") == ("dead", b"", "http_404")
    _patch(monkeypatch, response=_resp(503))
    assert fetch_mod.fetch_url("http", "h:1", "u", "xml") == ("fail", b"", "http_503")
    _patch(monkeypatch, response=_resp(200, b"<html>captcha</html>"))
    assert fetch_mod.fetch_url("http", "h:1", "u", "xml") == ("fail", b"", "content_marker_missing")


def _patch(monkeypatch, **kw):
    monkeypatch.setattr(fetch_mod.cffi, "Session", lambda **_: _Session(**kw))


def _resp(status, content=b""):
    return SimpleNamespace(status_code=status, content=content)


class _Session:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def get(self, url, **kw):
        if self._exc is not None:
            raise self._exc
        return self._response
