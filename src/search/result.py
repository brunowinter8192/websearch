# INFRASTRUCTURE
from dataclasses import dataclass, field


# FUNCTIONS

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    engine: str
    position: int
    preview: dict | None = None
    engines: list[str] = field(default_factory=list)
    snippets: dict[str, str] = field(default_factory=dict)
    engine_positions: dict[str, int] = field(default_factory=dict)
    date: str | None = None
    pdf_url: str | None = None
