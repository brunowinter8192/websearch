import pytest

from src.scraper import camoufox_scrape
from dev.tests._camoufox_scrape_fakes import _fake_launch_options, _make_fake_camoufox, _FakeAsyncWebCrawler


# ---------------------------------------------------------------------------
# Calibration surface: _build_camoufox_kwargs / _extract_camoufox_config_stamp
# ---------------------------------------------------------------------------

def test_build_camoufox_kwargs_reflects_block_images_param():
    """block_images is the one parameterized (per-lane) knob; everything else is fixed."""
    off = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    on = camoufox_scrape._build_camoufox_kwargs(block_images=True)
    assert off["block_images"] is False
    assert on["block_images"] is True


def test_build_camoufox_kwargs_fixed_decisions():
    """headless=False (visible window), os="macos" (matches real host), timeout explicit, locale
    resolved (as of 2026-08-27, so this lane requests the same language chromium gets for free from
    the OS) — and the deliberately-left-unset knobs (block_webgl, geoip, humanize, enable_cache,
    proxy) are truly ABSENT from the dict, not just False, so camoufox's own library defaults apply
    untouched."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["headless"] is False
    assert kwargs["os"] == "macos"
    assert kwargs["timeout"] == camoufox_scrape._PLAYWRIGHT_DEFAULT_TIMEOUT_MS
    assert isinstance(kwargs["locale"], str) and kwargs["locale"]
    for absent_key in ("block_webgl", "geoip", "humanize", "enable_cache", "proxy"):
        assert absent_key not in kwargs


def test_extract_camoufox_config_stamp_reads_real_executable_path_not_redeclared():
    """The stamp's executable_path comes off the REAL resolved launch_options() output, not a
    re-declared literal — changing what launch_options() resolves changes the stamp."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    resolved = {"executable_path": "/some/real/resolved/path", "headless": False}
    stamp = camoufox_scrape._extract_camoufox_config_stamp(kwargs, resolved)
    assert stamp["executable_path"] == "/some/real/resolved/path"
    assert stamp["total_budget_s"] == camoufox_scrape.TOTAL_CAMOUFOX_BUDGET_S


def test_extract_camoufox_config_stamp_excludes_randomized_fingerprint_data():
    """The stamp must NOT include per-launch randomized fingerprint data (fonts/seeds/env) even if
    present in the resolved dict — hashing that would make config_hash unique on every call."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    resolved = {
        "executable_path": "/some/path",
        "env": {"CAMOU_CONFIG": '{"canvas:seed": 12345}'},
        "firefox_user_prefs": {"some.random.pref": True},
    }
    stamp = camoufox_scrape._extract_camoufox_config_stamp(kwargs, resolved)
    assert "env" not in stamp
    assert "firefox_user_prefs" not in stamp


@pytest.mark.asyncio
async def test_config_hash_stable_for_identical_kwargs(monkeypatch):
    """Two calls with the same calibration surface produce the same config_hash — a real 'same
    config' grouping key, not per-call noise."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta1 = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")
    _, meta2 = await camoufox_scrape.try_scrape_camoufox("https://x.test/b")

    assert meta1["config_hash"] == meta2["config_hash"]


# ---------------------------------------------------------------------------
# scrape_url_camoufox_workflow: milestone 2 — the ad-hoc CLI wiring. Logs into the SAME
# scrape_log.jsonl / log_scrape / write_sidecar as chromium_scrape.py's chromium lane, discriminated by
# the "engine" field. try_scrape_camoufox is faked at the module boundary; log_scrape/write_sidecar
# are faked to capture the record instead of touching the filesystem.
# ---------------------------------------------------------------------------

def _meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "landed_url": "https://x.test/a",
        "raw_markdown_bytes": 100, "markdown_conversion_error": None,
        "document_status_chain": [200],
        "config": {"headless": False}, "config_hash": "deadbeef00",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_engine_discriminator(monkeypatch):
    """The logged record carries engine="camoufox" — the first-class discriminator this milestone
    adds, distinguishing it from the chromium lane's engine="chromium" records in the same file."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "real markdown content", _meta()
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["engine"] == "camoufox"
    assert captured["url"] == "https://x.test/a"
    assert captured["mode"] == "markdown"
    assert "outcome" not in captured


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_acquisition_error_as_its_own_fact(monkeypatch):
    """No computed outcome anymore — acquisition_error (try_scrape_camoufox's own fact field:
    "budget_exhausted"/"browser_missing"/"exception", or None) is logged straight through as its
    own field, the same precedent pipe_scraper_records.py's _log_pipe_camoufox_record set."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "", _meta(acquisition_error="budget_exhausted", status_code=None, landed_url=None)
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["acquisition_error"] == "budget_exhausted"


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_document_status_chain(monkeypatch):
    """scrape_url_camoufox_workflow's log_scrape record carries the new fact field."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "real content", _meta(document_status_chain=[403, 302, 200])
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["document_status_chain"] == [403, 302, 200]


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_does_not_double_hash_config(monkeypatch):
    """config_hash is read straight off meta (computed once, inside try_scrape_camoufox) — the
    workflow must not re-hash it itself."""
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "content", _meta(config_hash="already-computed-hash")
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["config_hash"] == "already-computed-hash"


# ---------------------------------------------------------------------------
# _format_camoufox_output: minimal shape — heading + content, no facts block
# ---------------------------------------------------------------------------

def test_format_camoufox_output_normal_markdown_shape():
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "the real markdown content here")
    assert "# Content from: https://x.test/a" in text
    assert "the real markdown content here" in text


def test_format_camoufox_output_acquisition_failure_shape():
    text = camoufox_scrape._format_camoufox_output("https://x.test/a", "")
    assert "(no content returned)" in text


# ---------------------------------------------------------------------------
# M2 milestone (2026-09-15): the printed acquisition-facts block is removed entirely — the facts
# still exist, they just stop being printed. Output shrinks; the log record does not.
# ---------------------------------------------------------------------------

def test_format_camoufox_output_carries_no_acquisition_facts_preamble():
    text = camoufox_scrape._format_camoufox_output("https://x.test/a", "the real page content")
    assert "Acquisition facts" not in text
    assert "the real page content" in text


@pytest.mark.asyncio
async def test_scrape_url_camoufox_workflow_logs_full_field_set_unchanged(monkeypatch):
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "real content", _meta()

    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    expected_fields = {
        "ts", "url", "domain", "mode", "engine", "acquisition_error", "timings_ms",
        "http_status", "bytes_returned", "bytes_raw_markdown", "content_path", "landed_url",
        "markdown_conversion_error", "document_status_chain", "config_hash", "config",
    }
    assert expected_fields <= captured.keys()
