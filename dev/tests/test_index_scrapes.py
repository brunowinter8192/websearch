import subprocess

import src.scraper.index_scrapes as index_scrapes


def _write_sidecar(sidecar_dir, ts, url, content):
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    slug = index_scrapes._url_slug(url)
    filename = f"{ts.replace(':', '-')}_{slug}.md"
    header = (
        f"<!-- url: {url} -->\n"
        f"<!-- ts: {ts} -->\n"
        f"<!-- bytes: {len(content.encode('utf-8'))} -->\n"
        f"<!-- mode: filtered -->\n"
        f"<!-- engine: chromium -->\n"
    )
    (sidecar_dir / filename).write_text(header + "\n" + content, encoding="utf-8")
    return sidecar_dir / filename


def _raising_run(*args, **kwargs):
    raise AssertionError("subprocess.run must not be called")


def test_find_sidecar_picks_latest_among_multiple_scrapes(tmp_path):
    sidecar_dir = tmp_path / "scrape_content"
    url = "https://www.mojeek.com/search?q=python+asyncio+tutorial"
    _write_sidecar(sidecar_dir, "2026-09-17T16:41:00.707Z", url, "# Verification required")
    _write_sidecar(sidecar_dir, "2026-09-17T16:53:41.001Z", url, "# real content, long body")
    latest = _write_sidecar(sidecar_dir, "2026-09-17T16:54:15.360Z", url, "# Verification required")
    other_url = "https://www.mojeek.com/search?q=rust+ownership+model"
    _write_sidecar(sidecar_dir, "2026-09-17T16:45:05.246Z", other_url, "# unrelated")

    found = index_scrapes._find_sidecar(url, sidecar_dir)

    assert found == latest


def test_find_sidecar_returns_none_when_no_match(tmp_path):
    sidecar_dir = tmp_path / "scrape_content"
    sidecar_dir.mkdir(parents=True)
    assert index_scrapes._find_sidecar("https://example.com/nope", sidecar_dir) is None


def test_write_collection_file_matches_convention(tmp_path):
    collection_dir = tmp_path / "some-collection"
    collection_dir.mkdir()
    url = "https://api.semanticscholar.org/graph/v1/swagger.json"
    filename = index_scrapes._url_to_filename(url)

    byte_count = index_scrapes._write_collection_file(collection_dir, filename, url, "body text")

    assert filename == "api_semanticscholar_org_graph_v1_swagger_json.md"
    written = (collection_dir / filename).read_text(encoding="utf-8")
    lines = written.split("\n")
    assert lines[0] == f"<!-- source: {url} -->"
    assert lines[1] == ""
    assert lines[2] == "body text"
    assert byte_count == len(written.encode("utf-8"))


def test_sidecar_content_strips_header(tmp_path):
    sidecar_dir = tmp_path / "scrape_content"
    path = _write_sidecar(sidecar_dir, "2026-09-20T10:00:00.000Z", "https://example.com/x",
                           "real body\nsecond line")

    content = index_scrapes._sidecar_content(path)

    assert content == "real body\nsecond line"
    assert "<!-- url:" not in content


def test_index_one_no_sidecar_never_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _raising_run)
    sidecar_dir = tmp_path / "scrape_content"
    sidecar_dir.mkdir()
    collection_dir = tmp_path / "col"
    collection_dir.mkdir()

    outcome = index_scrapes._index_one("https://example.com/nope", sidecar_dir, "col", collection_dir)

    assert outcome.status == "no_sidecar"
    assert outcome.detail == ""


def test_index_one_success(tmp_path, monkeypatch):
    sidecar_dir = tmp_path / "scrape_content"
    url = "https://example.com/real-page"
    _write_sidecar(sidecar_dir, "2026-09-20T10:00:00.000Z", url, "real content body")
    collection_dir = tmp_path / "col"
    collection_dir.mkdir()

    calls = []

    def _fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    outcome = index_scrapes._index_one(url, sidecar_dir, "col", collection_dir)

    assert outcome.status == "indexed"
    assert outcome.detail == index_scrapes._url_to_filename(url)
    assert outcome.byte_count == len((collection_dir / outcome.detail).read_bytes())
    assert calls == [["rag-cli", "index", "--collection", "col", "--document", outcome.detail]]


def test_index_one_rag_cli_failure_reports_failed(tmp_path, monkeypatch):
    sidecar_dir = tmp_path / "scrape_content"
    url = "https://example.com/real-page"
    _write_sidecar(sidecar_dir, "2026-09-20T10:00:00.000Z", url, "real content body")
    collection_dir = tmp_path / "col"
    collection_dir.mkdir()

    def _fake_run(cmd, capture_output, text):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="collection not found")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    outcome = index_scrapes._index_one(url, sidecar_dir, "col", collection_dir)

    assert outcome.status == "failed"
    assert outcome.detail == "collection not found"


def test_workflow_aborts_when_collection_directory_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(index_scrapes, "RAG_CLI_COLLECTIONS_ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", _raising_run)

    result = index_scrapes.index_scrapes_workflow("does-not-exist", ["https://example.com/x"])

    assert result.ok is False
    assert "does-not-exist" in result.error
    assert result.outcomes == []
    assert not (tmp_path / "does-not-exist").exists()


def test_workflow_end_to_end(tmp_path, monkeypatch):
    collections_root = tmp_path / "documents"
    collection_dir = collections_root / "my-collection"
    collection_dir.mkdir(parents=True)
    monkeypatch.setattr(index_scrapes, "RAG_CLI_COLLECTIONS_ROOT", collections_root)

    sidecar_dir = tmp_path / "logdir" / "scrape_content"
    monkeypatch.setenv("WEBSEARCH_SCRAPE_LOG_PATH", str(tmp_path / "logdir" / "scrape_log.jsonl"))
    found_url = "https://example.com/found"
    missing_url = "https://example.com/missing"
    _write_sidecar(sidecar_dir, "2026-09-20T10:00:00.000Z", found_url, "content body")

    monkeypatch.setattr(subprocess, "run",
                         lambda cmd, capture_output, text: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""))

    result = index_scrapes.index_scrapes_workflow("my-collection", [found_url, missing_url])

    assert result.ok is True
    statuses = {o.url: o.status for o in result.outcomes}
    assert statuses[found_url] == "indexed"
    assert statuses[missing_url] == "no_sidecar"
