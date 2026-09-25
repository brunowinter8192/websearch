# INFRASTRUCTURE
import http.server
import json
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from _fixture_site_content import (
    DEFAULT_HOST, NAVTREE_CANONICAL_PAGES, NAVTREE_V1_ONLY_PAGES, RSC_DEMO_ROOT, RSC_DEMO_CHILDREN,
    ROBOTS_DISALLOW_PATHS, ROBOTS_ALLOW_PATHS, ROBOTS_EMPTY_404_PATHS,
    SITEMAP_BLOG_PAGES, SITEMAP_LEGAL_PAGES, THIN_BODY_HTML,
    ground_truth, seed_url, _build_routes,
)

_ROUTES: dict = {}
_STATE_LOCK = threading.Lock()
_STATE = {"request_count": 0, "rate_limit_limit": None, "rate_limit_window_s": None, "thin_body": False}
_REQUEST_TIMESTAMPS: list = []


# FUNCTIONS

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


def stop_fixture_server(server: http.server.ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/_control/"):
            self._serve_control()
        else:
            self._serve_content()

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
