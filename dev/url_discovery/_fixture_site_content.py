# INFRASTRUCTURE
import json
from urllib.parse import urljoin

DEFAULT_HOST = "127.0.0.1"

CURRENT_VERSION = "current"
ALL_VERSIONS = ("current", "v2", "v1")
SEED_PATH = "/docs/guide"
SEED_CONTENT_PATH = "/guide"

NAVTREE_CANONICAL_PAGES = (
    "/docs/guide",
    "/docs/guide/intro",
    "/docs/guide/configuration",
    "/docs/guide/configuration/advanced",
    "/docs/guide/api",
)
NAVTREE_V1_ONLY_PAGES = (
    "/docs/guide/legacy-plugin-api",
    "/docs/guide/legacy-theme-format",
)

RSC_DEMO_ROOT = "/rsc-demo"
RSC_DEMO_CHILDREN = ("/rsc-demo/alpha", "/rsc-demo/beta")

SITEMAP_INDEX_PATH = "/sitemap_index.xml"
SITEMAP_GROUP_PATH = "/sitemap-docs-group.xml"
SITEMAP_BLOG_LEAF_PATH = "/sitemap-blog.xml"
SITEMAP_LEGAL_LEAF_PATH = "/sitemap-legal.xml"
SITEMAP_BLOG_PAGES = ("/blog/post-1", "/blog/post-2", "/blog/post-3")
SITEMAP_LEGAL_PAGES = ("/legal/privacy", "/legal/terms")

ROBOTS_DISALLOW_PATHS = ("/internal/admin", "/internal/staging-notes")
ROBOTS_ALLOW_PATHS = ("/internal/public-notice",)
ROBOTS_REAL_PATHS = ("/internal/admin", "/internal/public-notice")
ROBOTS_EMPTY_404_PATHS = ("/internal/staging-notes",)

THIN_BODY_HTML = '<html><body><div id="app"></div></body></html>'


# FUNCTIONS

def seed_url(port: int, host: str = DEFAULT_HOST) -> str:
    return f"http://{host}:{port}{SEED_PATH}"


def _version_path(path: str, version: str) -> str:
    if version == CURRENT_VERSION:
        return path
    return path.replace("/docs/", f"/docs/{version}/", 1)


def _sidebar_tree(hrefs: tuple) -> dict:
    root, intro, configuration, configuration_advanced, api, *extra = hrefs
    children = [
        {"href": intro, "childPages": []},
        {"href": configuration, "childPages": [{"href": configuration_advanced, "childPages": []}]},
        {"href": api, "childPages": []},
    ]
    children += [{"href": h, "childPages": []} for h in extra]
    return {"href": root, "childPages": children}


def _next_data_page_html(tree: dict, title: str, with_version_meta: bool = False,
                         extra_links: tuple = ()) -> str:
    main_context = {"sidebarTree": tree}
    if with_version_meta:
        main_context.update({
            "allVersions": {v: {"version": v} for v in ALL_VERSIONS},
            "currentVersion": CURRENT_VERSION,
            "currentPathWithoutLanguage": SEED_CONTENT_PATH,
        })
    payload = {"props": {"pageProps": {"mainContext": main_context}}}
    links_html = "".join(f'<p><a href="{href}">{href}</a></p>' for href in extra_links)
    return (
        f"<html><head><title>{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>Fixture documentation page with real visible text, so it is never mistaken for a "
        f"thin anti-bot shell by crawl4ai's own structural check.</p>"
        f"{links_html}"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
        f"</body></html>"
    )


def _leaf_page_html(title: str, links: tuple = ()) -> str:
    links_html = "".join(f'<p><a href="{href}">{href}</a></p>' for href in links)
    return (
        f"<html><head><title>{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>Fixture content page for the url_discovery test site. This paragraph exists so the "
        f"page carries enough visible text to never read as an anti-bot block page.</p>"
        f"{links_html}"
        f"</body></html>"
    )


def _rsc_demo_html() -> str:
    tree = {"type": "root", "name": "RSC Demo", "children": [
        {"type": "page", "name": "Alpha", "url": RSC_DEMO_CHILDREN[0]},
        {"type": "page", "name": "Beta", "url": RSC_DEMO_CHILDREN[1]},
    ]}
    row = f"1:{json.dumps({'tree': tree})}"
    return (
        "<html><head><title>RSC demo</title></head><body>"
        "<h1>RSC demo (App Router payload shape)</h1>"
        "<p>Isolated demo page, deliberately never linked from the main site graph — exists "
        "solely to exercise the self.__next_f.push RSC-stream extractor directly, since "
        "discover_urls_workflow only ever calls the navtree feeder once, against the main site's "
        "own Pages-Router shape.</p>"
        f"<script>self.__next_f.push([1,{json.dumps(row)}])</script>"
        "</body></html>"
    )


def _robots_txt(base_url: str) -> str:
    lines = ["User-agent: *"]
    lines += [f"Disallow: {p}" for p in ROBOTS_DISALLOW_PATHS]
    lines += [f"Allow: {p}" for p in ROBOTS_ALLOW_PATHS]
    lines.append(f"Sitemap: {urljoin(base_url, SITEMAP_INDEX_PATH)}")
    return "\n".join(lines) + "\n"


def _sitemapindex_xml(base_url: str, sub_paths: tuple) -> str:
    entries = "".join(f"<sitemap><loc>{urljoin(base_url, p)}</loc></sitemap>" for p in sub_paths)
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</sitemapindex>')


def _urlset_xml(base_url: str, paths: tuple) -> str:
    entries = "".join(f"<url><loc>{urljoin(base_url, p)}</loc></url>" for p in paths)
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>')


def _homepage_html() -> str:
    return (
        "<html><head><title>url_discovery fixture site</title></head><body>"
        "<h1>url_discovery fixture site</h1>"
        "<p>Deterministic fixture for src/crawler/discovery.py. This page is never linked from "
        "anywhere and never appears in any discovery run. See dev/url_discovery/_fixture_site.py "
        "for the ground truth and GET /_control/status for live failure-mode state.</p>"
        "</body></html>"
    )


def _build_routes(base_url: str) -> dict:
    routes = {}

    def add(path, content_type, body):
        routes[path] = (200, content_type, body.encode("utf-8"))

    add("/", "text/html; charset=utf-8", _homepage_html())

    current_tree = _sidebar_tree(NAVTREE_CANONICAL_PAGES)
    add(SEED_PATH, "text/html; charset=utf-8", _next_data_page_html(
        current_tree, title="Guide (current)", with_version_meta=True))
    for path in NAVTREE_CANONICAL_PAGES[1:]:
        add(path, "text/html; charset=utf-8", _leaf_page_html(title=f"Guide: {path}"))
    for path in NAVTREE_V1_ONLY_PAGES:
        add(path, "text/html; charset=utf-8", _leaf_page_html(title=f"Guide (v1-only): {path}"))

    v2_hrefs = tuple(_version_path(p, "v2") for p in NAVTREE_CANONICAL_PAGES)
    add(_version_path(SEED_PATH, "v2"), "text/html; charset=utf-8", _next_data_page_html(
        _sidebar_tree(v2_hrefs), title="Guide (v2)"))
    v1_hrefs = (tuple(_version_path(p, "v1") for p in NAVTREE_CANONICAL_PAGES)
                + tuple(_version_path(p, "v1") for p in NAVTREE_V1_ONLY_PAGES))
    add(_version_path(SEED_PATH, "v1"), "text/html; charset=utf-8", _next_data_page_html(
        _sidebar_tree(v1_hrefs), title="Guide (v1)"))

    for path in SITEMAP_BLOG_PAGES + SITEMAP_LEGAL_PAGES:
        add(path, "text/html; charset=utf-8", _leaf_page_html(title=f"Blog/legal: {path}"))
    for path in ROBOTS_REAL_PATHS:
        add(path, "text/html; charset=utf-8", _leaf_page_html(title=f"Internal: {path}"))

    add("/robots.txt", "text/plain; charset=utf-8", _robots_txt(base_url))
    add(SITEMAP_INDEX_PATH, "application/xml; charset=utf-8",
        _sitemapindex_xml(base_url, (SITEMAP_GROUP_PATH,)))
    add(SITEMAP_GROUP_PATH, "application/xml; charset=utf-8",
        _sitemapindex_xml(base_url, (SITEMAP_BLOG_LEAF_PATH, SITEMAP_LEGAL_LEAF_PATH)))
    add(SITEMAP_BLOG_LEAF_PATH, "application/xml; charset=utf-8", _urlset_xml(base_url, SITEMAP_BLOG_PAGES))
    add(SITEMAP_LEGAL_LEAF_PATH, "application/xml; charset=utf-8", _urlset_xml(base_url, SITEMAP_LEGAL_PAGES))

    add(RSC_DEMO_ROOT, "text/html; charset=utf-8", _rsc_demo_html())
    for path in RSC_DEMO_CHILDREN:
        add(path, "text/html; charset=utf-8", _leaf_page_html(title=f"RSC demo: {path}"))

    return routes


def _expected_seeds() -> list:
    order = []
    seen = set()

    def add(paths, tag):
        for p in paths:
            if p not in seen:
                seen.add(p)
                order.append((p, tag))

    add((SEED_PATH,), "seed")
    add(ROBOTS_DISALLOW_PATHS + ROBOTS_ALLOW_PATHS, "robots")
    add(SITEMAP_BLOG_PAGES + SITEMAP_LEGAL_PAGES, "sitemap_declared")
    add(NAVTREE_CANONICAL_PAGES + NAVTREE_V1_ONLY_PAGES, "navtree_tree")
    return order


def ground_truth() -> dict:
    seeds = _expected_seeds()
    by_source = {}
    for _, tag in seeds:
        by_source[tag] = by_source.get(tag, 0) + 1
    return {
        "seed_path": SEED_PATH,
        "total_urls": len(seeds),
        "by_source": by_source,
        "navtree": {
            "total": len(set(NAVTREE_CANONICAL_PAGES) | set(NAVTREE_V1_ONLY_PAGES)),
            "canonical": len(NAVTREE_CANONICAL_PAGES),
            "version_exclusive": len(NAVTREE_V1_ONLY_PAGES),
            "version_exclusive_pages": list(NAVTREE_V1_ONLY_PAGES),
        },
        "sitemap": {"listed": len(SITEMAP_BLOG_PAGES) + len(SITEMAP_LEGAL_PAGES)},
        "robots": {"listed": len(ROBOTS_DISALLOW_PATHS) + len(ROBOTS_ALLOW_PATHS)},
    }
