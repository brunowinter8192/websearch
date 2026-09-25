# INFRASTRUCTURE
import importlib
import logging
import sys

import pytest


# FUNCTIONS

def test_importing_cli_has_no_side_effects(monkeypatch, tmp_path):
    root_handlers = list(logging.getLogger().handlers)
    registered = []
    monkeypatch.setattr("atexit.register", lambda fn, *a, **kw: registered.append(fn))
    monkeypatch.delitem(sys.modules, "cli", raising=False)
    importlib.import_module("cli")
    sys.modules.pop("cli", None)
    assert logging.getLogger().handlers == root_handlers
    assert registered == []


def test_configure_logging_creates_log_dir_and_installs_one_rotating_file_handler(cli_module, monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    handler_calls = []
    basic_calls = []
    sentinel = logging.NullHandler()
    monkeypatch.setattr(cli_module, "LOG_DIR", log_dir)
    monkeypatch.setattr(cli_module, "get_retention_days", lambda: 7)
    monkeypatch.setattr(cli_module, "TimedRotatingFileHandler", lambda *a, **kw: handler_calls.append((a, kw)) or sentinel)
    monkeypatch.setattr(cli_module.logging, "basicConfig", lambda **kw: basic_calls.append(kw))
    cli_module.configure_logging()
    assert log_dir.is_dir()
    (args, kwargs), = handler_calls
    assert args == (log_dir / "cli.log",)
    assert kwargs == {"when": "midnight", "interval": 1, "backupCount": 7, "encoding": "utf-8"}
    (basic,) = basic_calls
    assert basic["handlers"] == [sentinel]
    assert basic["level"] == logging.DEBUG


def test_register_exit_hook_registers_the_browser_cleanup(cli_module, monkeypatch):
    registered = []
    monkeypatch.setattr(cli_module.atexit, "register", registered.append)
    cli_module.register_exit_hook()
    assert registered == [cli_module.kill_own_chrome_atexit]


def test_main_configures_logging_before_parsing_arguments(cli_module, monkeypatch):
    order = []
    monkeypatch.setattr(cli_module, "configure_logging", lambda: order.append("logging"))
    monkeypatch.setattr(cli_module, "register_exit_hook", lambda: order.append("hook"))

    class _Parser:
        def parse_args(self):
            order.append("parse")
            return type("A", (), {"cmd": "none"})()

    monkeypatch.setattr(cli_module, "build_parser", lambda: _Parser())
    cli_module.main()
    assert order == ["logging", "hook", "parse"]


@pytest.fixture
def cli_module(monkeypatch):
    monkeypatch.delitem(sys.modules, "cli", raising=False)
    module = importlib.import_module("cli")
    yield module
    sys.modules.pop("cli", None)
