# INFRASTRUCTURE
import html as html_lib
import http.server
import threading
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

DEFAULT_HOST = "127.0.0.1"
RESULTS_PATH = "/search"

_ROUTES: dict = {}


@dataclass
class ResultSpec:
    title: str
    snippet: str
    date: str | None
    token: str
    behavior: str = "ok"
    target: str | None = None


HAPPY_SPECS = [
    ResultSpec(
        title="The Best ANC Headphones to Buy in 2025",
        snippet="The Sennheiser HDB 630 is considered by many to be the best ANC headphone on "
                "the market currently, and for good reason. It doesn't have noise\xa0...",
        date="21 Nov 2025", token="ok1", target="t1",
    ),
    ResultSpec(
        title="The 4 Best Noise-Cancelling Headphones of 2026",
        snippet="Soundcore Liberty 5 Pro. These earbuds have excellent noise cancellation, and "
                "they employ the best noise-reducing microphones we've tested. But\xa0...",
        date="7 days ago", token="ok2", target="t2",
    ),
    ResultSpec(
        title="Best Noise Cancelling Headphones 2026 (50+ Tested!)",
        snippet="Our 2025 noise cancelling award winner from last year was the Sony XM6, with its "
                "excellent “QN3” processing chip that delivers impressive real-time adjustments\xa0...",
        date=None, token="ok3", target="t3",
    ),
    ResultSpec(
        title="The 5 Best Noise Cancelling Headphones of 2026",
        snippet="The Sony WH-1000XM6 are the best noise cancelling headphones we've tested. "
                "These premium over-ears have remarkable noise isolation.",
        date="26 Aug 2026", token="ok4", target="t4",
    ),
    ResultSpec(
        title="Best noise-cancelling headphones 2026 – 6 sensational ...",
        snippet="Our current pick as the best noise-cancelling headphones, the Sony WH-1000XM6 "
                "– which you will find at number one in our list on this very page\xa0...",
        date="24 Jul 2026", token="ok5", target="t5",
    ),
    ResultSpec(
        title="I've tested all of 2025's best noise-cancelling headphones, but ...",
        snippet="The best ANC headphones are plentiful, with 2025 bringing a new and significant "
                "entry to the shelves, in the form of Sony's WH-1000XM6 over-\xa0...",
        date="24 Jun 2025", token="ok6", target="t6",
    ),
    ResultSpec(
        title="Der beste Noise-Cancelling-Kopfhörer | Test 09/2026",
        snippet="Wir haben 108 Noise-Cancelling-Kopfhörer getestet. Testsieger Sony WH-1000XM6 "
                "liefert tolles ANC und eine umfassende App-Steuerung.",
        date="17 Jul 2026", token="ok7", target="t7",
    ),
    ResultSpec(
        title="Noise-Cancelling-Kopfhörer im Test: Die besten Over-Ears ...",
        snippet="Die zweite Generation der Bose QuietComfort Ultra Headphones überzeugt im Test "
                "mit einem tollen, sehr neutral abgestimmten Sound. Bässe sind ausgeglichen,\xa0...",
        date=None, token="ok8", target="t8",
    ),
]


# FUNCTIONS

def goto_url(port: int, token: str) -> str:
    return f"http://{DEFAULT_HOST}:{port}/goto?url={token}"


def results_page_url(port: int) -> str:
    return f"http://{DEFAULT_HOST}:{port}{RESULTS_PATH}"


def start_fixture_server(specs: list[ResultSpec], decoys: int = 0, host: str = DEFAULT_HOST, port: int = 0):
    global _ROUTES
    server = http.server.ThreadingHTTPServer((host, port), _FixtureHandler)
    bound_port = server.server_address[1]
    routes = _build_goto_routes(specs, bound_port)
    routes["__page__"] = build_results_html(specs, bound_port, decoys=decoys)
    _ROUTES = routes
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
        parsed = urlsplit(self.path)
        if parsed.path == "/goto":
            self._serve_goto(parsed)
        elif parsed.path == RESULTS_PATH:
            self._serve_results()
        elif parsed.path.startswith("/target/"):
            self._respond(200, b"<html><body>resolved target</body></html>", "text/html")
        else:
            self._respond(404, b"not found", "text/plain")

    def _serve_goto(self, parsed):
        token = parse_qs(parsed.query).get("url", [""])[0]
        route = _ROUTES.get(token)
        if route is None:
            self._respond(404, b"unknown token", "text/plain")
            return
        self.send_response(route["status"])
        if route["location"] is not None:
            self.send_header("Location", route["location"])
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_results(self):
        body = _ROUTES["__page__"].encode("utf-8")
        self._respond(200, body, "text/html")

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


def _build_goto_routes(specs: list[ResultSpec], port: int) -> dict:
    routes = {}
    for spec in specs:
        if spec.behavior == "ok":
            routes[spec.token] = {
                "status": 302,
                "location": f"http://{DEFAULT_HOST}:{port}/target/{spec.target}",
            }
        elif spec.behavior == "bad_status":
            routes[spec.token] = {"status": 404, "location": None}
        elif spec.behavior == "no_location":
            routes[spec.token] = {"status": 302, "location": None}
        elif spec.behavior == "bad_location":
            routes[spec.token] = {"status": 302, "location": "/not/an/absolute/url"}
        else:
            raise ValueError(f"unknown ResultSpec.behavior: {spec.behavior!r}")
    return routes


def build_results_html(specs: list[ResultSpec], port: int, decoys: int = 0) -> str:
    containers = [_organic_container_html(s, port) for s in specs]
    containers.extend(_decoy_container_html() for _ in range(decoys))
    body = "\n".join(containers)
    return f"<!DOCTYPE html><html><body id=\"main\">{body}</body></html>"


def _organic_container_html(spec: ResultSpec, port: int) -> str:
    title = html_lib.escape(spec.title)
    snippet = html_lib.escape(spec.snippet)
    href = f"/goto?url={spec.token}"
    date_span = (
        f'<span class="YrbPuc"><span>{html_lib.escape(spec.date)}</span> — </span>'
        if spec.date else ""
    )
    return f"""
    <div class="MjjYud">
      <div class="A6K0A" data-rpos="1">
        <div class="N54PNb BToiNc" data-snc="x">
          <div class="kb0PBd A9Y9g" data-snf="x5WNvb" data-snhf="0">
            <div class="yuRUbf">
              <div class="b8lM7">
                <span class="V9tjod">
                  <a class="zReHs" jsname="UWckNb" href="{href}">
                    <h3 class="LC20lb MBeuO DKV0Md">{title}</h3>
                    <br>
                    <div class="notranslate ESMNde HGLrXd ojE3Fb">
                      <div class="q0vns">
                        <div class="CA5RN"><div><span class="VuuXrf">Example</span></div>
                          <div class="byrV5b"><cite class="qLRx3b tjvcx GvPZzd cHaqb">example.com</cite></div>
                        </div>
                      </div>
                    </div>
                  </a>
                </span>
              </div>
            </div>
          </div>
          <div class="kb0PBd A9Y9g" data-sncf="1" data-snf="nke7rc">
            <div class="VwiC3b yXK7lf p4wth r025kc Hdw6tb">{date_span}<span>{snippet}</span><a class="vzmbzf" href="/goto?url=readmore_inert">Read more</a></div>
          </div>
        </div>
      </div>
    </div>
    """


def _decoy_container_html() -> str:
    return """
    <div class="MjjYud">
      <div class="related-question-pair">
        <div class="related-question-title">People also ask</div>
      </div>
    </div>
    """
