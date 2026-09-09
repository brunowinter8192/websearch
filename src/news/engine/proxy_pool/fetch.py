# INFRASTRUCTURE

from curl_cffi import requests as cffi

XML_MARKERS   = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")
HTML_MARKERS  = (b"<html", b"<!DOCTYPE", b"<!doctype")
FETCH_TIMEOUT = 15


# ORCHESTRATOR

def fetch_url(proto: str, host_port: str, url: str, content_type: str) -> tuple[str, bytes]:
    purl = f"{proto}://{host_port}"
    try:
        s = cffi.Session(impersonate="chrome")
        r = s.get(url, proxies={"http": purl, "https": purl}, timeout=FETCH_TIMEOUT)
        return _validate(r, content_type)
    except Exception:
        return "fail", b""


# FUNCTIONS

def _validate(r, content_type: str) -> tuple[str, bytes]:
    if r.status_code in (404, 410):
        return "dead", b""
    if r.status_code != 200:
        return "fail", b""
    head = r.content[:500]
    if content_type == "xml":
        ok = any(m in head for m in XML_MARKERS)
    elif content_type == "html":
        ok = any(m in head.lower() for m in HTML_MARKERS)
    else:
        ok = False
    return ("ok", r.content) if ok else ("fail", b"")
