import logging

import src.search.browser as browser


class _R:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _patch(monkeypatch, result):
    monkeypatch.setattr(browser, "_osascript_warned", set())
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **kw: result)


def test_frontmost_pid_warns_once_when_stdout_is_not_a_pid(monkeypatch, caplog):
    _patch(monkeypatch, _R(0, ""))
    with caplog.at_level(logging.WARNING, logger="src.search.browser"):
        assert browser._get_frontmost_pid() is None
        assert browser._get_frontmost_pid() is None
    assert len([m for m in caplog.messages if "get_frontmost" in m]) == 1


def test_frontmost_pid_warns_on_nonzero_exit(monkeypatch, caplog):
    _patch(monkeypatch, _R(1, "", "not allowed"))
    with caplog.at_level(logging.WARNING, logger="src.search.browser"):
        browser._get_frontmost_pid()
    assert any("not allowed" in m for m in caplog.messages)


def test_frontmost_pid_silent_on_success(monkeypatch, caplog):
    _patch(monkeypatch, _R(0, "123\n"))
    with caplog.at_level(logging.WARNING, logger="src.search.browser"):
        assert browser._get_frontmost_pid() == 123
    assert caplog.messages == []


def test_activate_pid_warns_once_on_nonzero_exit(monkeypatch, caplog):
    _patch(monkeypatch, _R(1, "", "denied"))
    with caplog.at_level(logging.WARNING, logger="src.search.browser"):
        browser._activate_pid(5)
        browser._activate_pid(5)
    assert len(caplog.messages) == 1
