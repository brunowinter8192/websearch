# INFRASTRUCTURE
import gzip
from xml.etree import ElementTree

import httpx
import pytest

from src.crawler.seed_feeders_scope import FeederResult
from src.crawler.seed_feeders_sitemap import fetch_sitemap, parse_sitemap_xml, resolve_sitemap_urls
from src.crawler import seed_feeders
from dev.tests._seed_feeders_fakes import _FakeResponse, _FakeAsyncClient, _RaisingAsyncClient, _xml


# FUNCTIONS

def test_parse_sitemap_xml_urlset():
    content = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/a</loc></url>"
        "<url><loc>https://example.com/b</loc></url>"
        "</urlset>"
    )
    kind, urls = parse_sitemap_xml(content)
    assert kind == "urlset"
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_parse_sitemap_xml_sitemapindex():
    content = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/sub1.xml</loc></sitemap>"
        "<sitemap><loc>https://example.com/sub2.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    kind, urls = parse_sitemap_xml(content)
    assert kind == "index"
    assert urls == ["https://example.com/sub1.xml", "https://example.com/sub2.xml"]


def test_parse_sitemap_xml_malformed_raises_parse_error():
    with pytest.raises(ElementTree.ParseError):
        parse_sitemap_xml(b"not xml at all <<<")


def test_parse_sitemap_xml_unrelated_root_returns_unknown():
    kind, urls = parse_sitemap_xml(_xml("<rss><channel/></rss>"))
    assert (kind, urls) == ("unknown", [])


@pytest.mark.asyncio
async def test_fetch_sitemap_404_returns_none_not_error():
    client = _FakeAsyncClient({})
    content = await fetch_sitemap(client, "https://example.com/sitemap.xml")
    assert content is None


@pytest.mark.asyncio
async def test_resolve_sitemap_urls_flattens_two_level_nesting():
    top = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/mid.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    mid = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/leaf.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    leaf = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/page1</loc></url>"
        "<url><loc>https://example.com/page2</loc></url>"
        "</urlset>"
    )
    client = _FakeAsyncClient({
        "https://example.com/top.xml": _FakeResponse(200, content=top),
        "https://example.com/mid.xml": _FakeResponse(200, content=mid),
        "https://example.com/leaf.xml": _FakeResponse(200, content=leaf),
    })
    urls = await resolve_sitemap_urls(client, ["https://example.com/top.xml"])
    assert sorted(urls) == ["https://example.com/page1", "https://example.com/page2"]


@pytest.mark.asyncio
async def test_resolve_sitemap_urls_one_404_sub_is_normal_not_fatal():
    top = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/ok.xml</loc></sitemap>"
        "<sitemap><loc>https://example.com/missing.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    ok_leaf = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/page1</loc></url>"
        "</urlset>"
    )
    client = _FakeAsyncClient({
        "https://example.com/top.xml": _FakeResponse(200, content=top),
        "https://example.com/ok.xml": _FakeResponse(200, content=ok_leaf),
    })
    urls = await resolve_sitemap_urls(client, ["https://example.com/top.xml"])
    assert urls == ["https://example.com/page1"]


@pytest.mark.asyncio
async def test_resolve_sitemap_urls_cycle_guard_does_not_hang():
    a = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/b.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    b = _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.com/a.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    client = _FakeAsyncClient({
        "https://example.com/a.xml": _FakeResponse(200, content=a),
        "https://example.com/b.xml": _FakeResponse(200, content=b),
    })
    urls = await resolve_sitemap_urls(client, ["https://example.com/a.xml"])
    assert urls == []


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_prefers_robots_declared_sitemap(monkeypatch):
    robots_text = "Sitemap: https://docs.example.com/declared.xml\n"
    urlset = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://docs.example.com/a</loc></url>"
        "</urlset>"
    )
    routes = {
        "https://docs.example.com/robots.txt": _FakeResponse(200, text=robots_text),
        "https://docs.example.com/declared.xml": _FakeResponse(200, content=urlset),
    }
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.urls == ["https://docs.example.com/a"]


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_falls_back_to_conventional_paths(monkeypatch):
    urlset = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://docs.example.com/a</loc></url>"
        "</urlset>"
    )
    routes = {
        "https://docs.example.com/sitemap.xml": _FakeResponse(200, content=urlset),
    }
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.urls == ["https://docs.example.com/a"]


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_all_404_is_ok_empty_docs_github_shape(monkeypatch):
    routes = {
        "https://docs.example.com/robots.txt": _FakeResponse(200, text="User-agent: *\nDisallow: /a\n"),
    }
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result == FeederResult(urls=[], ok=True, source="sitemap_conventional")


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_drops_foreign_host_urls(monkeypatch):
    urlset = _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://docs.example.com/a</loc></url>"
        "<url><loc>https://evil.example.org/b</loc></url>"
        "</urlset>"
    )
    routes = {"https://docs.example.com/sitemap.xml": _FakeResponse(200, content=urlset)}
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.urls == ["https://docs.example.com/a"]


@pytest.mark.asyncio
async def test_fetch_sitemap_network_error_propagates():
    client = _RaisingAsyncClient(httpx.ReadTimeout("read timed out"))
    with pytest.raises(httpx.ReadTimeout):
        await fetch_sitemap(client, "https://example.com/sitemap.xml")


@pytest.mark.asyncio
async def test_fetch_sitemap_corrupt_gz_raises():
    client = _FakeAsyncClient({"https://example.com/sitemap.xml.gz": _FakeResponse(200, content=b"not gzip data")})
    with pytest.raises(OSError):
        await fetch_sitemap(client, "https://example.com/sitemap.xml.gz")


@pytest.mark.asyncio
async def test_fetch_sitemap_valid_gz_is_decompressed():
    body = _xml("<urlset/>")
    client = _FakeAsyncClient({"https://example.com/sitemap.xml.gz": _FakeResponse(200, content=gzip.compress(body))})
    assert await fetch_sitemap(client, "https://example.com/sitemap.xml.gz") == body


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_non_xml_sitemap_is_failed_with_error(monkeypatch):
    routes = {
        "https://docs.example.com/robots.txt": _FakeResponse(404),
        "https://docs.example.com/sitemap.xml": _FakeResponse(200, content=b"<html><body>app shell</body>"),
    }
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.ok is False
    assert result.urls == []
    assert result.error


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_declared_route_is_named_in_source(monkeypatch):
    urlset = _xml('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://docs.example.com/a</loc></url></urlset>')
    routes = {
        "https://docs.example.com/robots.txt": _FakeResponse(200, text="Sitemap: https://docs.example.com/declared.xml\n"),
        "https://docs.example.com/declared.xml": _FakeResponse(200, content=urlset),
    }
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))
    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.source == "sitemap_declared"


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_conventional_route_is_named_in_source(monkeypatch):
    urlset = _xml('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://docs.example.com/a</loc></url></urlset>')
    routes = {"https://docs.example.com/sitemap.xml": _FakeResponse(200, content=urlset)}
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))
    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.source == "sitemap_conventional"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 410])
async def test_fetch_sitemap_absent_statuses_return_none(status):
    client = _FakeAsyncClient({"https://example.com/s.xml": _FakeResponse(status)})
    assert await fetch_sitemap(client, "https://example.com/s.xml") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429, 500, 503])
async def test_fetch_sitemap_other_non_200_raises(status):
    client = _FakeAsyncClient({"https://example.com/s.xml": _FakeResponse(status)})
    with pytest.raises(RuntimeError, match=str(status)):
        await fetch_sitemap(client, "https://example.com/s.xml")


@pytest.mark.asyncio
async def test_sitemap_feeder_workflow_server_error_is_failed_not_empty(monkeypatch):
    routes = {"https://docs.example.com/robots.txt": _FakeResponse(503)}
    monkeypatch.setattr(seed_feeders.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))
    result = await seed_feeders.sitemap_feeder_workflow("https://docs.example.com/")
    assert result.ok is False
    assert "503" in result.error
