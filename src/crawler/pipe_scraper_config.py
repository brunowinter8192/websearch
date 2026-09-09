# INFRASTRUCTURE
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from src.crawler.pipe_scraper_constants import PAGE_TIMEOUT_MS, DELAY_BEFORE_RETURN_HTML

# FUNCTIONS

def _build_configs() -> tuple[BrowserConfig, CrawlerRunConfig]:
    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False,
        enable_stealth=True,
    )
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_BEFORE_RETURN_HTML,
        page_timeout=PAGE_TIMEOUT_MS,
        markdown_generator=DefaultMarkdownGenerator(),
        simulate_user=True,
        override_navigator=True,
        magic=False,
        remove_consent_popups=True,
        verbose=False,
    )
    return browser_cfg, run_cfg

def _extract_pipe_config_stamp(
    browser_cfg: BrowserConfig,
    run_cfg: CrawlerRunConfig,
    download_delay: float,
    concurrency_per_domain: int,
) -> dict:
    return {
        "headless": browser_cfg.headless,
        "enable_stealth": browser_cfg.enable_stealth,
        "wait_until": run_cfg.wait_until,
        "page_timeout_ms": run_cfg.page_timeout,
        "delay_before_return_html_s": run_cfg.delay_before_return_html,
        "cache_mode": run_cfg.cache_mode.value,
        "simulate_user": run_cfg.simulate_user,
        "override_navigator": run_cfg.override_navigator,
        "magic": run_cfg.magic,
        "remove_consent_popups": run_cfg.remove_consent_popups,
        "download_delay_s": download_delay,
        "concurrency_per_domain": concurrency_per_domain,
    }
