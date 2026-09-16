import json
from datetime import datetime, timezone

import pytest

from src.crawler import pipe_scraper
from src.crawler import pipe_scraper_acquisition
from src.crawler import pipe_scraper_constants
from dev.tests._pipe_scraper_fakes import _FakeCrawler, _camoufox_meta


# ---------------------------------------------------------------------------
# Engine switch — milestone 3 of the camoufox_lane area: a per-RUN choice between the chromium
# engine (default, unchanged) and the camoufox engine (try_scrape_camoufox), never per-URL, never
# auto-selected. pipe_scraper_acquisition.try_scrape_camoufox is faked at the module boundary (same convention
# as camoufox_scrape's own tests faking AsyncCamoufox) — no real browser launched here either.
# ---------------------------------------------------------------------------

def test_camoufox_concurrency_default_is_conservative():
    """No measurement exists yet for how many concurrent Camoufox instances this machine
    tolerates — the default must be the most conservative value (fully serialized), unlike the
    chromium engine's measured/validated 8."""
    assert pipe_scraper_constants.CAMOUFOX_CONCURRENCY_PER_DOMAIN == 1
    assert pipe_scraper_constants.CAMOUFOX_CONCURRENCY_PER_DOMAIN < pipe_scraper_constants.CONCURRENCY_PER_DOMAIN


@pytest.mark.asyncio
async def test_scrape_all_default_engine_is_chromium_and_unchanged(tmp_path, monkeypatch):
    """engine defaulted/omitted -> the existing chromium path runs, untouched: AsyncWebCrawler is
    used, try_scrape_camoufox is never called at all."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append(url)
        return "should never be reached", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    assert called == []
    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["engine"] == "chromium"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_engine_dispatches_to_try_scrape_camoufox(tmp_path, monkeypatch):
    """engine="camoufox" -> try_scrape_camoufox is called per URL; AsyncWebCrawler/AsyncCamoufox
    (the chromium engine's own machinery) is never touched."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    class _UnreachableCrawler:
        def __init__(self, *a, **kw):
            raise AssertionError("chromium engine's AsyncWebCrawler must not be constructed")
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _UnreachableCrawler)

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append((url, block_images))
        return "# real markdown, non-trivial content" * 2, _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(
        ["https://x.test/a"], output_dir, download_delay=0.01,
        concurrency_per_domain=None, engine="camoufox", block_images=True,
    )

    assert called == [("https://x.test/a", True)]
    assert results[0]["status_code"] == 200
    assert (output_dir / pipe_scraper_acquisition._url_to_filename("https://x.test/a")).exists()


@pytest.mark.asyncio
async def test_scrape_all_camoufox_default_block_images_is_false(tmp_path, monkeypatch):
    """block_images omitted -> defaults to False, unified with the ad-hoc lane's own default
    (settled decision: stealth over bandwidth, per Camoufox's own LeakWarning on image-blocking
    as a WAF detection signal) — no longer True as the pipe engine used to default."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append((url, block_images))
        return "# real markdown, non-trivial content" * 2, _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(
        ["https://x.test/a"], output_dir, download_delay=0.01,
        concurrency_per_domain=None, engine="camoufox",
    )

    assert called == [("https://x.test/a", False)]


@pytest.mark.asyncio
async def test_scrape_all_camoufox_engine_resolves_own_concurrency_default(tmp_path, monkeypatch):
    """concurrency_per_domain=None + engine="camoufox" -> resolves to
    CAMOUFOX_CONCURRENCY_PER_DOMAIN, not the chromium default. Proven via timing: 3 same-domain
    URLs at concurrency=1 must serialize through the pacing gate (spread > 0), unlike the
    chromium default of 8 which would let them all start together."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "# content", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    urls = [f"https://x.test/{i}" for i in range(3)]
    await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.05,
                                    concurrency_per_domain=None, engine="camoufox")

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    timestamps = [datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in records]
    spread_s = (max(timestamps) - min(timestamps)).total_seconds()
    assert spread_s > 0.05, f"records did not serialize (spread={spread_s}s) — concurrency default was not 1"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_record_shape_engine_specific_fields(tmp_path, monkeypatch):
    """The camoufox-engine record carries engine="camoufox", landed_url,
    markdown_conversion_error, acquisition_error (try_scrape_camoufox's own fact field, logged
    directly — None here since this meta doesn't set it) — and does NOT carry the chromium-only
    crawl4ai_* fields at all (absent, not null/false)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "<html>raw</html>", _camoufox_meta(
            markdown_conversion_error="Invalid IPv6 URL",
            landed_url="https://landed.test/a",
        )
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=1, engine="camoufox")

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["engine"] == "camoufox"
    assert r["landed_url"] == "https://landed.test/a"
    assert r["markdown_conversion_error"] == "Invalid IPv6 URL"
    assert r["acquisition_error"] is None
    for chromium_only_key in ("crawl4ai_success", "crawl4ai_error_message", "crawl4ai_attempts",
                              "crawl4ai_resolved_by", "crawl4ai_fallback_fetch_used"):
        assert chromium_only_key not in r


@pytest.mark.asyncio
async def test_scrape_all_chromium_record_shape_camoufox_fields_absent(tmp_path, monkeypatch):
    """The chromium-engine record does NOT carry the camoufox-only markdown_conversion_error/
    acquisition_error fields at all (absent, not null/false) — symmetric with the test above."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["engine"] == "chromium"
    for camoufox_only_key in ("markdown_conversion_error", "acquisition_error"):
        assert camoufox_only_key not in r


@pytest.mark.asyncio
async def test_scrape_all_camoufox_acquisition_error_is_logged_as_its_own_fact(tmp_path, monkeypatch):
    """A hard acquisition failure (budget_exhausted/browser_missing/exception) is logged verbatim
    as its own fact, not collapsed into a computed verdict — try_scrape_camoufox already knows
    exactly which of the three it was; that specific value is what lands in the record, alongside
    the plain status_code=None/bytes=0 facts a total acquisition failure naturally produces."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "", _camoufox_meta(acquisition_error="browser_missing", status_code=None,
                                   landed_url=None)
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert results[0]["status_code"] is None
    assert results[0]["bytes"] == 0

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["acquisition_error"] == "browser_missing"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_resolved_challenge_status_flows_through_as_recorded_fact(tmp_path, monkeypatch):
    """M2: try_scrape_camoufox now reports the LAST main-frame document response's status, not a
    stale challenge-page status. A meta shaped like a resolved Cloudflare challenge (status_code=200
    from the corrected acquisition primitive, document_status_chain=[403, 302, 200] as the fact
    trail) must flow through as the recorded http_status=200 — no special-casing of the chain
    anywhere in this module, it only ever reads meta['status_code'] and passes it straight to the
    log. The JSONL record also carries the chain field."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return ("# real page content" * 3,
                _camoufox_meta(status_code=200, document_status_chain=[403, 302, 200]))
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert results[0]["status_code"] == 200
    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["http_status"] == 200
    assert records[0]["document_status_chain"] == [403, 302, 200]
