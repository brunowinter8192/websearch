import json

import httpx
import pytest

from src.crawler.seed_feeders_scope import FeederResult
from src.crawler.seed_feeders_navtree import (
    extract_payloads, find_navigation_tree, _build_version_urls, canonicalize_version_url,
    resolve_navigation_tree,
)
from src.crawler import navtree_feeder
from dev.tests._seed_feeders_fakes import _FakeResponse, _FakeAsyncClient, _RaisingAsyncClient, _next_data_html, _rsc_html


def test_extract_payloads_detects_next_data_shape():
    html = _next_data_html({"props": {"pageProps": {"a": 1}}})
    payloads = extract_payloads(html)
    assert payloads == [{"props": {"pageProps": {"a": 1}}}]


def test_extract_payloads_detects_rsc_stream_shape():
    html = _rsc_html(['1:{"a":1}', '2:{"b":2}'])
    payloads = extract_payloads(html)
    assert {"a": 1} in payloads
    assert {"b": 2} in payloads


def test_extract_payloads_rsc_skips_non_json_import_rows_without_erroring():
    html = _rsc_html(['1:I[437976,["chunk.js"]]', '2:{"real":"data"}'])
    payloads = extract_payloads(html)
    assert payloads == [{"real": "data"}]


def test_extract_payloads_neither_shape_returns_empty():
    html = "<html><body>plain page, no framework payload</body></html>"
    assert extract_payloads(html) == []


def test_find_navigation_tree_walks_recursive_tree():
    payload = {
        "url": "/docs",
        "children": [
            {"url": "/docs/a"},
            {"url": "/docs/b", "children": [{"url": "/docs/b/c"}]},
        ],
    }
    hrefs, tier, source = find_navigation_tree([payload])
    assert tier == "tree"
    assert source is payload
    assert sorted(hrefs) == ["/docs", "/docs/a", "/docs/b", "/docs/b/c"]


def test_find_navigation_tree_picks_the_largest_candidate():
    payload = {
        "smallWidget": {"href": "/x", "children": [{"href": "/x/a"}]},
        "realNav": {"href": "/docs", "children": [
            {"href": "/docs/a"}, {"href": "/docs/b"}, {"href": "/docs/c"},
        ]},
    }
    hrefs, tier, source = find_navigation_tree([payload])
    assert tier == "tree"
    assert sorted(hrefs) == ["/docs", "/docs/a", "/docs/b", "/docs/c"]


def test_find_navigation_tree_rejects_react_element_children_as_a_tree():
    payload = {
        "href": "/prev-page",
        "children": [["$", "svg", None, {}], ["$", "span", None, {"children": "Previous"}]],
    }
    hrefs, tier, source = find_navigation_tree([payload])
    assert tier == "flat"
    assert source is None
    assert hrefs == ["/prev-page"]


def test_find_navigation_tree_tier2_filters_fragment_and_internal_asset_paths():
    payload = {"links": [
        {"href": "/a"}, {"href": "#anchor-only"}, {"href": "/_next/static/chunk.css"}, {"href": ""},
    ]}
    hrefs, tier, source = find_navigation_tree([payload])
    assert tier == "flat"
    assert hrefs == ["/a"]


def test_find_navigation_tree_no_payloads_returns_empty_flat():
    assert find_navigation_tree([]) == ([], "flat", None)


def test_build_version_urls_constructs_url_per_other_version():
    all_versions = {"v1": {}, "v2": {}, "v3": {}}
    urls = _build_version_urls("https://x.test/de/guide", all_versions, "v1", "/guide")
    assert urls == {
        "v2": "https://x.test/de/v2/guide",
        "v3": "https://x.test/de/v3/guide",
    }
    assert "v1" not in urls


def test_build_version_urls_strips_version_prefix_when_seed_is_a_non_default_version():
    all_versions = {"v1": {}, "v2": {}}
    urls = _build_version_urls("https://x.test/de/v2/guide", all_versions, "v2", "/v2/guide")
    assert urls == {"v1": "https://x.test/de/v1/guide"}


def test_build_version_urls_empty_when_a_required_field_is_missing():
    assert _build_version_urls("https://x.test/de/guide", None, "v1", "/guide") == {}
    assert _build_version_urls("https://x.test/de/guide", {"v1": {}, "v2": {}}, None, "/guide") == {}
    assert _build_version_urls("https://x.test/de/guide", {"v1": {}, "v2": {}}, "v1", None) == {}


def test_build_version_urls_empty_when_content_path_not_a_suffix_of_seed():
    all_versions = {"v1": {}, "v2": {}}
    urls = _build_version_urls("https://x.test/de/guide", all_versions, "v1", "/unrelated-path")
    assert urls == {}


def test_canonicalize_version_url_strips_matching_segment_anywhere_in_path():
    url = "https://x.test/de/v2/guide/a"
    assert canonicalize_version_url(url, ["v1", "v2"]) == "https://x.test/de/guide/a"


def test_canonicalize_version_url_noop_when_no_marker_present():
    url = "https://x.test/de/guide/a"
    assert canonicalize_version_url(url, ["v1", "v2"]) == url


def test_canonicalize_version_url_preserves_query():
    url = "https://x.test/de/v2/guide?page=2"
    assert canonicalize_version_url(url, ["v2"]) == "https://x.test/de/guide?page=2"


@pytest.mark.asyncio
async def test_resolve_navigation_tree_unions_versions_and_dedups_via_canonicalization():
    default_payload = {"props": {"pageProps": {"mainContext": {
        "sidebarTree": {"href": "/de/guide", "childPages": [
            {"href": "/de/guide/intro", "childPages": []},
            {"href": "/de/guide/setup", "childPages": []},
        ]},
        "allVersions": {"v1": {"version": "v1"}, "v2": {"version": "v2"}},
        "currentVersion": "v1",
        "currentPathWithoutLanguage": "/guide",
    }}}}
    v2_payload = {"props": {"pageProps": {"mainContext": {
        "sidebarTree": {"href": "/de/v2/guide", "childPages": [
            {"href": "/de/v2/guide/intro", "childPages": []},
            {"href": "/de/v2/guide/legacy-page", "childPages": []},
        ]},
    }}}}
    routes = {
        "https://docs.example.com/de/guide": _FakeResponse(200, text=_next_data_html(default_payload)),
        "https://docs.example.com/de/v2/guide": _FakeResponse(200, text=_next_data_html(v2_payload)),
    }
    client = _FakeAsyncClient(routes)

    urls, tier, version_keys = await resolve_navigation_tree(client, "https://docs.example.com/de/guide")
    assert tier == "tree"
    assert sorted(set(urls)) == sorted([
        "https://docs.example.com/de/guide",
        "https://docs.example.com/de/guide/intro",
        "https://docs.example.com/de/guide/setup",
        "https://docs.example.com/de/guide/legacy-page",
    ])
    assert sorted(version_keys) == ["v1", "v2"]


@pytest.mark.asyncio
async def test_resolve_navigation_tree_unfetchable_seed_raises_not_empty():
    client = _FakeAsyncClient({})
    with pytest.raises(RuntimeError, match="could not fetch seed_url"):
        await resolve_navigation_tree(client, "https://docs.example.com/de/guide")


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_next_data_shape_end_to_end(monkeypatch):
    payload = {"tree": {"url": "/docs", "children": [{"url": "/docs/a"}, {"url": "/docs/b"}]}}
    routes = {"https://docs.example.com/": _FakeResponse(200, text=_next_data_html(payload))}
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.source == "navtree_tree"
    assert sorted(result.urls) == [
        "https://docs.example.com/docs", "https://docs.example.com/docs/a", "https://docs.example.com/docs/b",
    ]


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_rsc_tree_shape_does_not_fall_through(monkeypatch):
    rows = [
        '1:{"tree":{"type":"root","name":"Docs","children":['
        '{"type":"page","name":"A","url":"/docs/a"},'
        '{"type":"page","name":"B","url":"/docs/b"}]}}'
    ]
    routes = {"https://docs.example.com/": _FakeResponse(200, text=_rsc_html(rows))}
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.source == "navtree_tree"
    assert sorted(result.urls) == ["https://docs.example.com/docs/a", "https://docs.example.com/docs/b"]


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_rsc_dom_only_shape_falls_back_to_flat_tier(monkeypatch):
    rows = ['1:["$","a",null,{"href":"/docs/only-link","children":"Link text"}]']
    routes = {"https://docs.example.com/": _FakeResponse(200, text=_rsc_html(rows))}
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is True
    assert result.source == "navtree_flat"
    assert result.urls == ["https://docs.example.com/docs/only-link"]


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_neither_shape_is_ok_empty(monkeypatch):
    routes = {"https://docs.example.com/": _FakeResponse(200, text="<html>plain page</html>")}
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result == FeederResult(urls=[], ok=True, source="navtree_flat")


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_unreachable_seed_is_failed_not_ok_empty(monkeypatch):
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient({}))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is False
    assert result.urls == []
    assert result.source is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_invalid_seed_url_is_failed_not_empty():
    result = await navtree_feeder.navtree_feeder_workflow("not-a-url-at-all")
    assert result.ok is False
    assert result.urls == []
    assert result.error is not None


def test_extract_payloads_malformed_next_data_raises():
    html = '<html><script id="__NEXT_DATA__" type="application/json">{not json</script></html>'
    with pytest.raises(json.JSONDecodeError):
        extract_payloads(html)


@pytest.mark.asyncio
async def test_resolve_navigation_tree_network_error_on_seed_propagates():
    client = _RaisingAsyncClient(httpx.ConnectError("connection refused"))
    with pytest.raises(httpx.ConnectError):
        await resolve_navigation_tree(client, "https://docs.example.com/")


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_network_error_is_failed_with_error(monkeypatch):
    client = _RaisingAsyncClient(httpx.ConnectError("connection refused"))
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: client)

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is False
    assert result.urls == []
    assert "connection refused" in result.error


@pytest.mark.asyncio
async def test_navtree_feeder_workflow_malformed_next_data_is_failed_with_error(monkeypatch):
    html = '<html><script id="__NEXT_DATA__" type="application/json">{not json</script></html>'
    routes = {"https://docs.example.com/": _FakeResponse(200, text=html)}
    monkeypatch.setattr(navtree_feeder.httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(routes))

    result = await navtree_feeder.navtree_feeder_workflow("https://docs.example.com/")
    assert result.ok is False
    assert result.error


def _versioned_payload():
    return {"props": {"pageProps": {"mainContext": {
        "sidebarTree": {"href": "/de/guide", "childPages": [{"href": "/de/guide/intro", "childPages": []}]},
        "allVersions": {"v1": {"version": "v1"}, "v2": {"version": "v2"}},
        "currentVersion": "v1",
        "currentPathWithoutLanguage": "/guide",
    }}}}


@pytest.mark.asyncio
async def test_resolve_navigation_tree_absent_version_page_is_logged_and_skipped(caplog):
    routes = {"https://docs.example.com/de/guide": _FakeResponse(200, text=_next_data_html(_versioned_payload()))}
    client = _FakeAsyncClient(routes)
    with caplog.at_level("WARNING", logger="src.crawler.seed_feeders_navtree"):
        urls, _, _ = await resolve_navigation_tree(client, "https://docs.example.com/de/guide")
    assert "https://docs.example.com/de/guide/intro" in urls
    assert any("https://docs.example.com/de/v2/guide" in m for m in caplog.messages)


@pytest.mark.asyncio
async def test_resolve_navigation_tree_version_page_server_error_raises():
    routes = {
        "https://docs.example.com/de/guide": _FakeResponse(200, text=_next_data_html(_versioned_payload())),
        "https://docs.example.com/de/v2/guide": _FakeResponse(503),
    }
    client = _FakeAsyncClient(routes)
    with pytest.raises(RuntimeError, match="503"):
        await resolve_navigation_tree(client, "https://docs.example.com/de/guide")
