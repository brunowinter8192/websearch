"""Deterministic local fixture site for verifying src/crawler/discovery.py's three seed feeders
(robots.txt, sitemap, navtree) — the instrument process-docs/url_discovery/
2026-08-28_validation_against_live_sites_was_the_wrong_unit.md argues for: ground truth stated in
code (ground_truth(), below) rather than a number someone once measured on a live host, so a
discrepancy is either a real bug or a real fixture change, never an unresolvable "did the site
drift" question.

Every page/robots.txt/sitemap this module serves is GENERATED from the same source lists
ground_truth() reads its own numbers from (NAVTREE_CANONICAL_PAGES, SITEMAP_BLOG_PAGES, ...) — the
statement drives the pages, not the other way around.

Site shape (seed_url = seed_url(port), i.e. /docs/guide):
- Navtree (Pages Router __NEXT_DATA__, the shape src/crawler/seed_feeders_navtree.py's tier-1
  tree walk + version union both need): 3 versions of one doc tree (current/v2/v1), 2 pages that
  exist only in v1 (NAVTREE_V1_ONLY_PAGES) — the version-exclusive case.
- A separate, deliberately UNLINKED "/rsc-demo" island exercises the OTHER payload shape
  (self.__next_f.push RSC stream) directly via navtree_feeder_workflow — it is never part of the
  main site graph and never counted in ground_truth()'s totals.
- Sitemap: a TWO-LEVEL nested <sitemapindex> (sitemap_index.xml -> sitemap-docs-group.xml, itself
  an index -> two leaf <urlset> documents) — exercises resolve_sitemap_urls's recursion, not just
  one level of it.
- robots.txt: 2 Disallow + 1 Allow path, all collected as seeds regardless (the seed_feeders_robots
  decision this fixture must let happen, not prevent).

discover_urls_workflow itself never fetches a page — only the three feeders (robots.txt, a
sitemap, the seed page + its version roots) ever hit this server for a real discovery run, so
ground_truth() states exactly what those three feeders produce, nothing link-graph-derived. The
failure-mode switches below (/_control/*) predate that removal and remain for whichever future
caller (the scrape step, per src/crawler/DOCS.md) needs a fetch-failure/rate-limit target; no
current test exercises them.
"""
# INFRASTRUCTURE
import http.server
import json
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from _fixture_site_content import (  # noqa: E402
    DEFAULT_HOST, NAVTREE_CANONICAL_PAGES, NAVTREE_V1_ONLY_PAGES, RSC_DEMO_ROOT, RSC_DEMO_CHILDREN,
    ROBOTS_DISALLOW_PATHS, ROBOTS_ALLOW_PATHS, ROBOTS_EMPTY_404_PATHS,
    SITEMAP_BLOG_PAGES, SITEMAP_LEGAL_PAGES, THIN_BODY_HTML,
    ground_truth, seed_url, _build_routes,
)

_ROUTES: dict = {}
_STATE_LOCK = threading.Lock()
# rate_limit_limit/rate_limit_window_s: a SLIDING WINDOW, not an absolute counter that trips once
# and never recovers. The absolute-counter shape this replaced (process-docs/url_discovery/
# 2026-09-05_pacing_measurement.md) could not distinguish a well-paced crawler from a badly-paced
# one — both eventually send N total requests and both trip it identically, with no way back.
# A window lets a caller that spaces its requests stay under the limit indefinitely, and lets one
# that bursts recover once it slows down — the actual property real per-domain pacing needs to be
# checked against. _REQUEST_TIMESTAMPS holds one monotonic timestamp per non-control request
# admitted or checked while the window is armed; pruned to the trailing window on every check.
_STATE = {"request_count": 0, "rate_limit_limit": None, "rate_limit_window_s": None, "thin_body": False}
_REQUEST_TIMESTAMPS: list = []


# FUNCTIONS

# Serves the fixture site: normal content routes, the two switchable failure modes, and the
# /_control/* state endpoints — see the module docstring for the site shape.
class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/_control/"):
            self._serve_control()
        else:
            self._serve_content()

    # Read/mutate failure-mode state; never counted against the rate-limit window itself
    def _serve_control(self):
        global _REQUEST_TIMESTAMPS
        parsed = urlsplit(self.path)
        action = parsed.path[len("/_control/"):]
        params = parse_qs(parsed.query)
        with _STATE_LOCK:
            if action == "reset":
                _STATE.update(request_count=0, rate_limit_limit=None, rate_limit_window_s=None, thin_body=False)
                _REQUEST_TIMESTAMPS = []
            elif action == "rate_limit":
                _STATE["rate_limit_limit"] = int(params.get("limit", ["0"])[0])
                _STATE["rate_limit_window_s"] = float(params.get("window", ["1"])[0])
                _REQUEST_TIMESTAMPS = []
            elif action == "thin_body":
                _STATE["thin_body"] = params.get("on", ["true"])[0].lower() == "true"
            elif action != "status":
                self._respond(404, b"unknown control action", "text/plain")
                return
            reportable = dict(_STATE)
            reportable["requests_in_window"] = len(_REQUEST_TIMESTAMPS)
            body = json.dumps(reportable).encode("utf-8")
        self._respond(200, body, "application/json")

    # Normal content path: apply failure modes first (both override any real route), else serve
    # the built route or a genuine 404 (empty-body for ROBOTS_EMPTY_404_PATHS, a normal small body
    # for anything else unmapped)
    def _serve_content(self):
        with _STATE_LOCK:
            _STATE["request_count"] += 1
            limit = _STATE["rate_limit_limit"]
            window = _STATE["rate_limit_window_s"]
            thin_body = _STATE["thin_body"]
            over_limit = False
            if limit is not None:
                now = time.monotonic()
                cutoff = now - window
                while _REQUEST_TIMESTAMPS and _REQUEST_TIMESTAMPS[0] < cutoff:
                    _REQUEST_TIMESTAMPS.pop(0)
                if len(_REQUEST_TIMESTAMPS) >= limit:
                    over_limit = True
                else:
                    _REQUEST_TIMESTAMPS.append(now)

        if over_limit:
            self._respond(429, b"Too Many Requests", "text/plain")
            return
        if thin_body:
            self._respond(200, THIN_BODY_HTML.encode("utf-8"), "text/html")
            return
        if self.path in ROBOTS_EMPTY_404_PATHS:
            self._respond(404, b"", "text/html")
            return
        route = _ROUTES.get(self.path)
        if route is None:
            self._respond(404, b"not found", "text/plain")
            return
        status, content_type, body = route
        self._respond(status, body, content_type)

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


# Start the fixture on an OS-assigned free port (port=0) or a given one; builds every route fresh
# (base_url needs the real bound port for absolute sitemap <loc> URLs) and resets failure-mode
# state. Returns (server, thread, bound_port). Only ONE fixture server is meant to run per process
# at a time — routes/state are module-level, not per-instance (see Gotchas in DOCS.md).
def start_fixture_server(host: str = DEFAULT_HOST, port: int = 0):
    global _ROUTES, _REQUEST_TIMESTAMPS
    server = http.server.ThreadingHTTPServer((host, port), _FixtureHandler)
    bound_port = server.server_address[1]
    base_url = f"http://{host}:{bound_port}/"
    _ROUTES = _build_routes(base_url)
    with _STATE_LOCK:
        _STATE.update(request_count=0, rate_limit_limit=None, rate_limit_window_s=None, thin_body=False)
        _REQUEST_TIMESTAMPS = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, bound_port


# Shut the fixture server down cleanly
def stop_fixture_server(server: http.server.ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
