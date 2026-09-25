# INFRASTRUCTURE
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.news.engine.proxy_riding.scrape import RidingScrapeConfig


# FUNCTIONS

@dataclass
class ProxyScrapeConfig:
    pool_provider: Callable[[], tuple[list[tuple[str, str]], list[dict]]]
    content_type: str = "html"
    concurrency: int = 128
    buffer_size: int = 1280


@runtime_checkable
class Platform(Protocol):
    name: str
    collection: str
    precondition_url: str
    regwall_signals: list[str]
    scrape_engine: str
    scrape_config: ScrapeConfig
    proxy_scrape_config: "ProxyScrapeConfig | None"
    timeframe: str = "delta"
    uses_master_list: bool = False
    supports_scrape_only: bool = False
    riding_scrape_config: "RidingScrapeConfig | None" = None

    async def discover(self) -> list[dict]: ...

    def load_scrape_entries(
        self,
        year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...


@dataclass
class ScrapeConfig:
    download_delay: float = 1.0
    concurrency_per_domain: int = 8
    page_timeout_ms: int = 15000
    delay_before_return_html: float = 0.5
