# INFRASTRUCTURE
from src.news.platform import Platform, ScrapeConfig
from src.news.platforms.theblock.config import PROXY_SCRAPE_CONFIG
from src.news.platforms.theblock.discover import discover as _discover
from src.news.platforms.theblock.cleanup import cleanup as _cleanup


# FUNCTIONS

class TheBlockPlatform(Platform):
    name: str                  = "theblock"
    collection: str            = "theblock"
    precondition_url: str      = "https://www.google.com"
    regwall_signals: list[str] = []
    scrape_engine: str         = "proxy_pool"
    scrape_config: ScrapeConfig = ScrapeConfig()
    proxy_scrape_config        = PROXY_SCRAPE_CONFIG
    timeframe: str             = "delta"
    dedup_mode: str            = "hash_only"
    uses_master_list: bool     = True

    async def discover(self, logger=None) -> list[dict]:
        return await _discover(self.timeframe, acquire_logger=logger)

    def cleanup(self, raw_html: str, entry: dict) -> str:
        return _cleanup(raw_html, entry)

