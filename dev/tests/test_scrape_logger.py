import src.scraper.scrape_logger as scrape_logger


def test_write_sidecar_header_includes_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_SCRAPE_LOG_PATH", str(tmp_path / "scrape_log.jsonl"))
    rel_path = scrape_logger.write_sidecar(
        "https://example.com/page", "2026-08-25T12:00:00.000Z", "real content", "filtered", "chromium",
    )
    assert rel_path is not None
    written = (tmp_path / rel_path).read_text(encoding="utf-8")
    assert "<!-- engine: chromium -->" in written
    assert "<!-- url: https://example.com/page -->" in written
    assert "<!-- mode: filtered -->" in written
    assert written.endswith("real content")


def test_write_sidecar_header_has_no_outcome_line(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_SCRAPE_LOG_PATH", str(tmp_path / "scrape_log.jsonl"))
    rel_path = scrape_logger.write_sidecar(
        "https://example.com/page", "2026-08-25T12:00:00.000Z", "real content", "filtered", "chromium",
    )
    written = (tmp_path / rel_path).read_text(encoding="utf-8")
    assert "outcome" not in written


def test_write_sidecar_header_reflects_camoufox_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_SCRAPE_LOG_PATH", str(tmp_path / "scrape_log.jsonl"))
    rel_path = scrape_logger.write_sidecar(
        "https://example.com/page", "2026-08-25T12:00:00.000Z", "real content", "markdown", "camoufox",
    )
    written = (tmp_path / rel_path).read_text(encoding="utf-8")
    assert "<!-- engine: camoufox -->" in written


def test_write_sidecar_returns_none_on_empty_content(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_SCRAPE_LOG_PATH", str(tmp_path / "scrape_log.jsonl"))
    assert scrape_logger.write_sidecar("https://x.test", "2026-08-25T12:00:00.000Z", "", "filtered", "chromium") is None
