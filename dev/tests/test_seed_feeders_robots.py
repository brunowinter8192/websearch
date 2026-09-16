import pytest

from src.crawler.seed_feeders_scope import FeederResult
from src.crawler.seed_feeders_robots import fetch_robots_txt, parse_robots_directives
from src.crawler import seed_feeders
from dev.tests._seed_feeders_fakes import _FakeResponse, _FakeAsyncClient


# ---------------------------------------------------------------------------
# parse_robots_directives — Allow/Disallow paths + Sitemap: lines
# ---------------------------------------------------------------------------

def test_parse_robots_directives_extracts_paths_and_sitemap():
    text = (
        "User-agent: *\n"
        "Disallow: /search\n"
        "Allow: /public/\n"
        "Sitemap: https://example.com/sitemap_index.xml\n"
    )
    result = parse_robots_directives(text, "https://example.com/")
    assert result["paths"] == ["https://example.com/search", "https://example.com/public/"]
    assert result["sitemaps"] == ["https://example.com/sitemap_index.xml"]


def test_parse_robots_directives_case_insensitive_and_comment_stripped():
    text = "DISALLOW: /a  # internal only\nsitemap: /sitemap.xml\n"
    result = parse_robots_directives(text, "https://example.com/")
    assert result["paths"] == ["https://example.com/a"]
    assert result["sitemaps"] == ["https://example.com/sitemap.xml"]


def test_parse_robots_directives_multiple_user_agent_blocks_all_collected():
    text = (
        "User-agent: *\nDisallow: /a\n\n"
        "User-agent: GPTBot\nDisallow: /b\nDisallow: /c\n"
    )
    result = parse_robots_directives(text, "https://example.com/")
    assert result["paths"] == [
        "https://example.com/a", "https://example.com/b", "https://example.com/c",
    ]


def test_parse_robots_directives_ignores_blank_and_unrelated_lines():
    text = "User-agent: *\n\n# comment only\nCrawl-delay: 10\nDisallow: /x\n"
    result = parse_robots_directives(text, "https://example.com/")
    assert result["paths"] == ["https://example.com/x"]


def test_parse_robots_directives_empty_value_dropped():
    text = "User-agent: *\nDisallow:\n"
    result = parse_robots_directives(text, "https://example.com/")
    assert result["paths"] == []


# ---------------------------------------------------------------------------
# fetch_robots_txt — DI'd fake client, no monkeypatching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_robots_txt_returns_text_on_200():
    client = _FakeAsyncClient({"https://example.com/robots.txt": _FakeResponse(200, text="Disallow: /a\n")})
    text = await fetch_robots_txt(client, "https://example.com/")
    assert text == "Disallow: /a\n"


@pytest.mark.asyncio
async def test_fetch_robots_txt_missing_returns_none_not_error():
    client = _FakeAsyncClient({})  # every URL 404s
    text = await fetch_robots_txt(client, "https://example.com/")
    assert text is None


# ---------------------------------------------------------------------------
# robots_feeder_workflow / sitemap_feeder_workflow — end-to-end, fake client injected
# via monkeypatching seed_feeders.httpx.AsyncClient (workflows construct it internally)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_robots_feeder_workflow_returns_scoped_paths(monkeypatch):
    robots_text = "User-agent: *\nDisallow: /internal/\nAllow: /public/\n"
    routes = {"https://docs.example.com/robots.txt": _FakeResponse(200, text=robots_text)}
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.robots_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.urls == [
        "https://docs.example.com/internal/", "https://docs.example.com/public/",
    ]


@pytest.mark.asyncio
async def test_robots_feeder_workflow_missing_robots_is_ok_empty(monkeypatch):
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient({}))

    result = await seed_feeders.robots_feeder_workflow("https://docs.example.com/")
    assert result == FeederResult(urls=[], ok=True, source="robots")


@pytest.mark.asyncio
async def test_robots_feeder_workflow_invalid_seed_url_is_failed_not_empty():
    result = await seed_feeders.robots_feeder_workflow("not-a-url-at-all")
    assert result.ok is False
    assert result.urls == []
    assert result.error is not None
