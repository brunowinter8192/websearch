# INFRASTRUCTURE
import json
import subprocess

import pytest

from src.code_version import UNKNOWN_VERSION, read_code_version
from src.crawler import pipe_scrape_logger
from src.scraper import scrape_logger
from src.search import query_logger


# FUNCTIONS

def test_clean_repo_reports_plain_sha(tmp_path):
    repo = _repo_with_tracked_file(tmp_path)

    version = read_code_version(repo)

    assert version == _git(repo, "rev-parse", "--short=10", "HEAD")


def test_modified_tracked_file_adds_dirty_suffix(tmp_path):
    repo = _repo_with_tracked_file(tmp_path)
    (repo / "tracked.txt").write_text("changed")

    version = read_code_version(repo)

    assert version == _git(repo, "rev-parse", "--short=10", "HEAD") + "+dirty"


def test_untracked_file_does_not_make_repo_dirty(tmp_path):
    repo = _repo_with_tracked_file(tmp_path)
    (repo / "untracked.txt").write_text("new")

    version = read_code_version(repo)

    assert not version.endswith("+dirty")


def test_directory_without_repo_reports_unknown(tmp_path):
    assert read_code_version(tmp_path) == UNKNOWN_VERSION


@pytest.mark.parametrize("env_name,writer_module,writer_name", [
    ("WEBSEARCH_QUERY_LOG_PATH", query_logger, "log_query"),
    ("WEBSEARCH_SCRAPE_LOG_PATH", scrape_logger, "log_scrape"),
    ("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", pipe_scrape_logger, "log_pipe_scrape"),
])
def test_every_log_writer_stamps_code_version(tmp_path, monkeypatch, env_name, writer_module, writer_name):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv(env_name, str(log_path))
    monkeypatch.setattr(writer_module, "code_version", lambda: "abc1234567")

    getattr(writer_module, writer_name)({"ts": "2026-10-12T00:00:00.000Z", "url": "https://example.com"})

    record = json.loads(log_path.read_text().splitlines()[0])
    assert record["code_version"] == "abc1234567"
    assert record["url"] == "https://example.com"


def _repo_with_tracked_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "tracked.txt").write_text("v1")
    _git(repo, "add", "tracked.txt")
    _git(repo, "-c", f"core.hooksPath={tmp_path / 'no_hooks'}", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    return repo


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()
