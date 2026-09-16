"""Tests for src/crawler/seed_feeders*.py — robots.txt + sitemap seed feeders.

Two layers. Pure-function, no network at all: fetch-layer tests inject a fake httpx client
directly (fetch_robots_txt/fetch_sitemap take `client` as a parameter — no monkeypatching
needed); workflow-level tests monkeypatch `seed_feeders.httpx.AsyncClient`, an established
fake-client pattern in this project's test suite. Fixture-backed, real network but only ever
against the local `dev/url_discovery/_fixture_site.py` server, never a live host (see
process-docs/url_discovery/2026-08-28_validation_against_live_sites_was_the_wrong_unit.md for
why): one shared module-scoped server for the whole file, each of the three feeders checked
against the exact fixture feature built for it — replacing the one-off, unrepeatable
docs.github.com/theblock.co/ui.shadcn.com/nextjs.org runs process-docs/url_discovery/
2026-08-28_robots_sitemap_seed_feeders.md and 2026-08-28_navtree_seed_feeder.md recorded.
"""
import pytest

from src.crawler import seed_feeders
from dev.url_discovery._fixture_site import (
    start_fixture_server, stop_fixture_server, seed_url, DEFAULT_HOST,
    RSC_DEMO_ROOT, RSC_DEMO_CHILDREN, ROBOTS_DISALLOW_PATHS, ROBOTS_ALLOW_PATHS,
    SITEMAP_BLOG_PAGES, SITEMAP_LEGAL_PAGES, NAVTREE_CANONICAL_PAGES, NAVTREE_V1_ONLY_PAGES,
)


# ---------------------------------------------------------------------------
# Fixture-backed checks (dev/url_discovery/_fixture_site.py) — real network, but only ever
# against the local fixture server, never a live host. One module-scoped server for the whole
# file (fixture_server below) — every test here shares the same real server, no per-test startup.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fixture_server():
    server, thread, port = start_fixture_server()
    yield port
    stop_fixture_server(server, thread)


def _fixture_url(port: int, path: str) -> str:
    return f"http://{DEFAULT_HOST}:{port}{path}"


@pytest.mark.asyncio
async def test_robots_feeder_against_fixture_collects_allow_and_disallow(fixture_server):
    # The deliberate behavior process-docs/url_discovery/2026-08-28_robots_sitemap_seed_feeders.md
    # documents: Allow AND Disallow paths are both collected as seeds, regardless of what they
    # permit — checked here against a stable local host instead of a one-off live snapshot.
    result = await seed_feeders.robots_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "robots"
    expected = {_fixture_url(fixture_server, p) for p in ROBOTS_DISALLOW_PATHS + ROBOTS_ALLOW_PATHS}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_sitemap_feeder_against_fixture_resolves_two_level_nested_index(fixture_server):
    # The recursive-resolution claim process-docs/url_discovery/2026-08-28_robots_sitemap_seed_
    # feeders.md verified against theblock.co's 63-sub-sitemap index — a live tree that changes
    # every run. This fixture's 2-level nesting (sitemap_index.xml -> sitemap-docs-group.xml,
    # itself an index -> two leaf urlsets) exercises the same recursion, with a result that never
    # drifts between runs.
    result = await seed_feeders.sitemap_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "sitemap"
    expected = {_fixture_url(fixture_server, p) for p in SITEMAP_BLOG_PAGES + SITEMAP_LEGAL_PAGES}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_navtree_feeder_against_fixture_unions_versions_and_recovers_oldest_only_pages(fixture_server):
    # The version-union claim process-docs/url_discovery/2026-08-28_navtree_seed_feeder.md
    # verified against docs.github.com (254 -> 304 URLs, a snapshot that has already drifted once
    # on record). This fixture's 3-version tree makes "2 pages exist only in the oldest version" an
    # exact, named set instead of an unlabeled part of a larger live count.
    result = await seed_feeders.navtree_feeder_workflow(seed_url(fixture_server))
    assert result.ok is True
    assert result.source == "navtree_tree"
    expected = {_fixture_url(fixture_server, p) for p in NAVTREE_CANONICAL_PAGES + NAVTREE_V1_ONLY_PAGES}
    assert set(result.urls) == expected


@pytest.mark.asyncio
async def test_navtree_feeder_against_fixture_detects_rsc_app_router_shape(fixture_server):
    # The OTHER payload shape process-docs/url_discovery/2026-08-28_navtree_seed_feeder.md
    # verified against ui.shadcn.com (substituted for the challenge-gated coindesk.com) — this
    # fixture's isolated /rsc-demo island exercises the same self.__next_f.push extractor
    # directly, deterministically, without depending on any third-party site being reachable.
    result = await seed_feeders.navtree_feeder_workflow(_fixture_url(fixture_server, RSC_DEMO_ROOT))
    assert result.ok is True
    assert result.source == "navtree_tree"
    expected = {_fixture_url(fixture_server, p) for p in RSC_DEMO_CHILDREN}
    assert set(result.urls) == expected
