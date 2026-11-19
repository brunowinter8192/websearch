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


def parse(parser, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", *argv])
    return parser.parse_args()


def test_pdf_subcommands_parse_their_flags(parser, monkeypatch):
    args = parse(parser, monkeypatch, "split", "--pdf", "a.pdf", "--batch-dir", "/tmp/x")
    assert (args.cmd, args.pdf_cmd, args.pdf, args.batch_dir) == ("pdf", "split", "a.pdf", "/tmp/x")
    args = parse(parser, monkeypatch, "resplit", "--batch-dir", "/tmp/x", "--piece", "51-100")
    assert (args.pdf_cmd, args.piece) == ("resplit", "51-100")
    for command in ("status", "merge", "sample", "sample-report"):
        assert parse(parser, monkeypatch, command, "--batch-dir", "/tmp/x").pdf_cmd == command
    assert parse(parser, monkeypatch, "sample-close", "--batch-dir", "/tmp/x").reject == []
    args = parse(parser, monkeypatch, "sample-close", "--batch-dir", "/tmp/x", "--reject", "17", "--reject", "22")
    assert args.reject == [17, 22]
    args = parse(parser, monkeypatch, "publish", "--batch-dir", "/tmp/x", "--out-dir", "/tmp/o")
    assert (args.pdf_cmd, args.out_dir) == ("publish", "/tmp/o")
    assert parse(parser, monkeypatch, "stats", "--since", "2026-10-01").since == "2026-10-01"


@pytest.mark.parametrize("argv", [["extract", "--pdf", "a.pdf", "--batch-dir", "/tmp/x"], ["assemble", "--batch-dir", "/tmp/x", "--out-dir", "/tmp/o"]])
def test_removed_pdf_subcommands_are_rejected(parser, monkeypatch, argv):
    with pytest.raises(SystemExit) as raised:
        parse(parser, monkeypatch, *argv)
    assert raised.value.code == 2


def test_pdf_stats_rejects_a_malformed_date(parser, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cli.py", "pdf", "stats", "--since", "10/01/2026"])
    with pytest.raises(SystemExit) as raised:
        parser.parse_args()
    assert raised.value.code == 2
