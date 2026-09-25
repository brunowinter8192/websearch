# INFRASTRUCTURE

from curl_cffi import requests as cffi
from curl_cffi.requests.exceptions import RequestException

from src.config import XML_MARKERS

HTML_MARKERS  = (b"<html", b"<!DOCTYPE", b"<!doctype")
FETCH_TIMEOUT = 15


# ORCHESTRATOR

def fetch_url(proto: str, host_port: str, url: str, content_type: str) -> tuple[str, bytes, str | None]:
    purl = _proxy_url(proto, host_port)
    s = cffi.Session(impersonate="chrome")
    return _get_and_validate(s, purl, url, content_type)


# FUNCTIONS

def _proxy_url(proto: str, host_port: str) -> str:
    return f"{proto}://{host_port}"


def _get_and_validate(s, purl: str, url: str, content_type: str) -> tuple[str, bytes, str | None]:
    try:
        r = s.get(url, proxies={"http": purl, "https": purl}, timeout=FETCH_TIMEOUT)
    except RequestException as exc:
        return "fail", b"", type(exc).__name__
    return _validate(r, content_type)


def _validate(r, content_type: str) -> tuple[str, bytes, str | None]:
    if r.status_code in (404, 410):
        return "dead", b"", f"http_{r.status_code}"
    if r.status_code != 200:
        return "fail", b"", f"http_{r.status_code}"
    head = r.content[:500]
    if content_type == "xml":
        ok = any(m in head for m in XML_MARKERS)
    elif content_type == "html":
        ok = any(m in head.lower() for m in HTML_MARKERS)
    else:
        ok = False
    return ("ok", r.content, None) if ok else ("fail", b"", "content_marker_missing")
