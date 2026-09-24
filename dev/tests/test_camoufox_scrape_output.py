import subprocess

import pytest

from src.scraper import camoufox_scrape
from dev.tests._camoufox_scrape_fakes import _fake_launch_options, _make_fake_camoufox, _FakeAsyncWebCrawler

_real_resolve_system_locale = camoufox_scrape._resolve_system_locale


def test_build_camoufox_kwargs_reflects_block_images_param():
    off = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    on = camoufox_scrape._build_camoufox_kwargs(block_images=True)
    assert off["block_images"] is False
    assert on["block_images"] is True


def test_build_camoufox_kwargs_fixed_decisions():
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["headless"] is False
    assert kwargs["os"] == "macos"
    assert kwargs["timeout"] == camoufox_scrape._PLAYWRIGHT_DEFAULT_TIMEOUT_MS
    assert isinstance(kwargs["locale"], str) and kwargs["locale"]
    for absent_key in ("block_webgl", "geoip", "humanize", "enable_cache", "proxy"):
        assert absent_key not in kwargs


def test_extract_camoufox_config_stamp_reads_real_executable_path_not_redeclared():
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    resolved = {"executable_path": "/some/real/resolved/path", "headless": False}
    stamp = camoufox_scrape._extract_camoufox_config_stamp(kwargs, resolved)
    assert stamp["executable_path"] == "/some/real/resolved/path"
    assert stamp["total_budget_s"] == camoufox_scrape.TOTAL_CAMOUFOX_BUDGET_S


def test_extract_camoufox_config_stamp_excludes_randomized_fingerprint_data():
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
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta1 = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")
    _, meta2 = await camoufox_scrape.try_scrape_camoufox("https://x.test/b")

    assert meta1["config_hash"] == meta2["config_hash"]


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
    captured = {}

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "content", _meta(config_hash="already-computed-hash")
    monkeypatch.setattr(camoufox_scrape, "try_scrape_camoufox", _fake_try_scrape_camoufox)
    monkeypatch.setattr(camoufox_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(camoufox_scrape, "log_scrape", lambda record: captured.update(record))

    await camoufox_scrape.scrape_url_camoufox_workflow("https://x.test/a")

    assert captured["config_hash"] == "already-computed-hash"


def test_format_camoufox_output_normal_markdown_shape():
    text = camoufox_scrape._format_camoufox_output(
        "https://x.test/a", "the real markdown content here")
    assert "# Content from: https://x.test/a" in text
    assert "the real markdown content here" in text


def test_format_camoufox_output_acquisition_failure_shape():
    text = camoufox_scrape._format_camoufox_output("https://x.test/a", "")
    assert "(no content returned)" in text


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


def test_resolve_system_locale_command_failure_propagates(monkeypatch):
    def _fail(*a, **kw):
        raise subprocess.CalledProcessError(1, ["defaults", "read", "-g", "AppleLocale"])
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    monkeypatch.setattr(camoufox_scrape.subprocess, "run", _fail)
    with pytest.raises(subprocess.CalledProcessError):
        _real_resolve_system_locale()


def test_resolve_system_locale_converts_apple_locale_to_bcp47(monkeypatch):
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    monkeypatch.setattr(
        camoufox_scrape.subprocess, "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout="de_DE\n", stderr=""),
    )
    assert _real_resolve_system_locale() == "de-DE"
