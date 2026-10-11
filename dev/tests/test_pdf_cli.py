# INFRASTRUCTURE
import importlib
import sys

import pytest


# FUNCTIONS

@pytest.fixture
def parser(monkeypatch):
    monkeypatch.delitem(sys.modules, "cli", raising=False)
    module = importlib.import_module("cli")
    yield module.build_parser()
    sys.modules.pop("cli", None)


def test_pdf_subcommands_parse_their_flags(parser, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", "extract", "--pdf", "a.pdf", "--batch-dir", "/tmp/x"])
    args = parser.parse_args()
    assert (args.cmd, args.pdf_cmd, args.pdf, args.batch_dir) == ("pdf", "extract", "a.pdf", "/tmp/x")
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", "assemble", "--batch-dir", "/tmp/x", "--out-dir", "/tmp/o"])
    args = parser.parse_args()
    assert (args.pdf_cmd, args.out_dir) == ("assemble", "/tmp/o")
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", "stats", "--since", "2026-10-01"])
    assert parser.parse_args().since == "2026-10-01"


def test_pdf_stats_rejects_a_malformed_date(parser, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", "stats", "--since", "10/01/2026"])
    with pytest.raises(SystemExit) as raised:
        parser.parse_args()
    assert raised.value.code == 2
