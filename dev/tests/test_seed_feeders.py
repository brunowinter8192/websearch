import pytest

from src.crawler.navtree_feeder import navtree_feeder_workflow
from src.crawler.robots_feeder import robots_feeder_workflow
from src.crawler.sitemap_feeder import sitemap_feeder_workflow
from dev.url_discovery._fixture_site import (
    start_fixture_server, stop_fixture_server, seed_url, DEFAULT_HOST,
    RSC_DEMO_ROOT, RSC_DEMO_CHILDREN, ROBOTS_DISALLOW_PATHS, ROBOTS_ALLOW_PATHS,
    SITEMAP_BLOG_PAGES, SITEMAP_LEGAL_PAGES, NAVTREE_CANONICAL_PAGES, NAVTREE_V1_ONLY_PAGES,
)


@pytest.fixture(scope="module")
def fixture_server():
    server, thread, port = start_fixture_server()
    yield port
    stop_fixture_server(server, thread)


def _fixture_url(port: int, path: str) -> str:
    return f"http://{DEFAULT_HOST}:{port}{path}"


@pytest.mark.asyncio
async def test_robots_feeder_against_fixture_collects_allow_and_disallow(fixture_server):
    result = await robots_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "robots"
    expected = {_fixture_url(fixture_server, p) for p in ROBOTS_DISALLOW_PATHS + ROBOTS_ALLOW_PATHS}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_sitemap_feeder_against_fixture_resolves_two_level_nested_index(fixture_server):
    result = await sitemap_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "sitemap_declared"
    expected = {_fixture_url(fixture_server, p) for p in SITEMAP_BLOG_PAGES + SITEMAP_LEGAL_PAGES}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_navtree_feeder_against_fixture_unions_versions_and_recovers_oldest_only_pages(fixture_server):
    result = await navtree_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "navtree_tree"
    expected = {_fixture_url(fixture_server, p) for p in NAVTREE_CANONICAL_PAGES + NAVTREE_V1_ONLY_PAGES}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_navtree_feeder_against_fixture_detects_rsc_app_router_shape(fixture_server):
    result = await navtree_feeder_workflow(_fixture_url(fixture_server, RSC_DEMO_ROOT))
    assert result.ok is True
    assert result.source == "navtree_tree"
    expected = {_fixture_url(fixture_server, p) for p in RSC_DEMO_CHILDREN}
    assert set(result.urls) == expected
