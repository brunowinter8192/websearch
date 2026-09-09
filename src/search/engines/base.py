# INFRASTRUCTURE
from abc import ABC, abstractmethod

from src.search.result import SearchResult


class BaseEngine(ABC):
    name: str

    @abstractmethod
    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None, dict | None]:
        ...

    async def search(self, query: str, language: str = "en", max_results: int = 10) -> list[SearchResult]:
        results, _, _ = await self.search_with_reason(query, language, max_results)
        return results
