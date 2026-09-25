# INFRASTRUCTURE
from src.config import REGWALL_SIGNALS
from src.news.platform import Platform, ScrapeConfig
from src.news.engine.proxy_riding.scrape import RidingScrapeConfig
from src.news.platforms.coindesk.config import SCRAPE_CONFIG, DISCOVER_DIR
from src.news.platforms.coindesk.discover import discover as _discover
from src.news.platforms.coindesk.shards import load_discover_filtered as _load_filtered
from src.news.platforms.coindesk.cleanup import cleanup as _cleanup


# FUNCTIONS

class CoinDeskPlatform(Platform):
    name: str = "coindesk"
    collection: str = "coindesk"
    precondition_url: str = "https://www.coindesk.com"
    regwall_signals: list[str] = REGWALL_SIGNALS
    scrape_engine: str = "proxy_riding"
    scrape_config: ScrapeConfig = SCRAPE_CONFIG
    proxy_scrape_config = None
    riding_scrape_config = RidingScrapeConfig()
    timeframe: str = "30"
    supports_scrape_only: bool = True

    async def discover(self) -> list[dict]:
        return await _discover(self.timeframe)

    def load_scrape_entries(
        self,
        year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return _load_filtered(DISCOVER_DIR, year=year, from_date=from_date, to_date=to_date, limit=limit)

    def cleanup(self, raw_markdown: str, entry: dict) -> str:
        return _cleanup(raw_markdown, entry)

