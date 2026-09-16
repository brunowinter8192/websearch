import pytest

from src.crawler import pipe_scraper_config
from src.crawler import pipe_scraper_constants


# ---------------------------------------------------------------------------
# _extract_pipe_config_stamp reads real objects, not re-declared literals
# ---------------------------------------------------------------------------

def test_extract_pipe_config_stamp_reads_real_objects():
    """The config stamp reflects the actual constructed BrowserConfig/CrawlerRunConfig values,
    not hardcoded copies — changing an object's value changes the stamp."""
    browser_cfg = pipe_scraper_config.BrowserConfig(headless=True, verbose=False, enable_stealth=True)
    run_cfg = pipe_scraper_config.CrawlerRunConfig(
        cache_mode=pipe_scraper_config.CacheMode.BYPASS,
        wait_until="networkidle",
        delay_before_return_html=1.25,
        page_timeout=9999,
    )
    stamp = pipe_scraper_config._extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay=2.0,
                                                             concurrency_per_domain=3)
    assert stamp["enable_stealth"] is True
    assert stamp["wait_until"] == "networkidle"
    assert stamp["page_timeout_ms"] == 9999
    assert stamp["delay_before_return_html_s"] == 1.25
    assert stamp["cache_mode"] == "bypass"
    assert stamp["download_delay_s"] == 2.0
    assert stamp["concurrency_per_domain"] == 3


def test_extract_pipe_config_stamp_reads_anti_bot_fields_off_real_objects():
    """simulate_user/override_navigator/magic/remove_consent_popups are read off the real
    CrawlerRunConfig, not re-declared — changing the object changes the stamp."""
    browser_cfg = pipe_scraper_config.BrowserConfig(headless=True, verbose=False)
    run_cfg = pipe_scraper_config.CrawlerRunConfig(
        simulate_user=True, override_navigator=True, magic=False, remove_consent_popups=True,
    )
    stamp = pipe_scraper_config._extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay=1.0,
                                                             concurrency_per_domain=8)
    assert stamp["simulate_user"] is True
    assert stamp["override_navigator"] is True
    assert stamp["magic"] is False
    assert stamp["remove_consent_popups"] is True


# ---------------------------------------------------------------------------
# _build_configs: the fixed anti-bot posture this milestone sets
# ---------------------------------------------------------------------------

def test_build_configs_sets_fixed_anti_bot_posture():
    """_build_configs's real BrowserConfig/CrawlerRunConfig carry the milestone's exact
    calibration: stealth + simulate_user + override_navigator on, magic explicitly off,
    consent popups dismissed, pacing/timeout values untouched."""
    browser_cfg, run_cfg = pipe_scraper_config._build_configs()
    assert browser_cfg.enable_stealth is True
    assert run_cfg.simulate_user is True
    assert run_cfg.override_navigator is True
    assert run_cfg.magic is False
    assert run_cfg.remove_consent_popups is True
    # Unchanged pacing/timeout values — no extraction-side settings added
    assert run_cfg.page_timeout == pipe_scraper_constants.PAGE_TIMEOUT_MS
    assert run_cfg.delay_before_return_html == pipe_scraper_constants.DELAY_BEFORE_RETURN_HTML
    assert run_cfg.markdown_generator.content_filter is None


@pytest.mark.asyncio
async def test_build_configs_produces_live_stealth_adapter():
    """Wiring test, not a dict comparison: constructs the REAL crawl4ai
    AsyncPlaywrightCrawlerStrategy from _build_configs's real BrowserConfig and asserts against
    crawl4ai's own BrowserManager/StealthAdapter state. No network — __init__ only builds state,
    never launches a browser. This is what a flag-only check (`browser_cfg.enable_stealth is
    True`) would NOT catch: StealthAdapter._check_stealth_availability swallows an ImportError
    and silently degrades `apply_stealth` to a no-op with no error raised anywhere (exactly what
    happened on crawl4ai 0.8.6 + playwright-stealth 2.0.2, see
    process-docs/scrape_pipeline/crawl4ai_stealth_stack_2026-05-31.md) — a dict check would still
    pass in that broken state, this test would not."""
    from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
    from playwright_stealth import Stealth

    browser_cfg, _ = pipe_scraper_config._build_configs()
    strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_cfg)

    # use_undetected resolves False (default PlaywrightAdapter, pipe_scraper passes no adapter) —
    # the precondition browser_manager.py requires to build the stealth adapter at all
    assert strategy.browser_manager.use_undetected is False
    assert strategy.browser_manager._stealth_adapter is not None
    assert strategy.browser_manager._stealth_adapter._stealth_available is True
    assert isinstance(strategy.browser_manager._stealth_adapter._stealth, Stealth)


# ---------------------------------------------------------------------------
# _build_configs(headed=...): M3 — the -g flag's config-level effect
# ---------------------------------------------------------------------------

def test_build_configs_default_stays_headless():
    """headed omitted -> headless=True, today's behavior unchanged."""
    browser_cfg, _ = pipe_scraper_config._build_configs()
    assert browser_cfg.headless is True


def test_build_configs_headed_true_sets_headless_false():
    browser_cfg, _ = pipe_scraper_config._build_configs(headed=True)
    assert browser_cfg.headless is False


def test_build_configs_headed_does_not_change_anti_bot_posture():
    """headed only flips headless — the fixed anti-bot calibration this module owns is
    untouched either way."""
    browser_cfg, run_cfg = pipe_scraper_config._build_configs(headed=True)
    assert browser_cfg.enable_stealth is True
    assert run_cfg.simulate_user is True
    assert run_cfg.override_navigator is True
    assert run_cfg.magic is False
    assert run_cfg.remove_consent_popups is True


def test_extract_pipe_config_stamp_reflects_headed():
    """The config stamp reads headless straight off the real object — no separate wiring
    needed for headed to reach the log."""
    browser_cfg, run_cfg = pipe_scraper_config._build_configs(headed=True)
    stamp = pipe_scraper_config._extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay=1.0,
                                                             concurrency_per_domain=8)
    assert stamp["headless"] is False
