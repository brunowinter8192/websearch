# INFRASTRUCTURE

import re

import httpx

from src.news.engine.proxy_pool.monosans_loader import load_monosans_proxies, MONOSANS_URL
from src.news.engine.proxy_pool.pool_retry import fetch_with_retry
from src.news.engine.proxy_pool.proxy_key import proxy_key

PROXIFLY_URL = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
FETCH_TIMEOUT = 15.0

THESPEEDX_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
]
JETKAI_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"),
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt"),
    ("socks4", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt"),
]
ROOSTERKID_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS.txt"),
    ("socks4", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4.txt"),
    ("socks5", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5.txt"),
]
THEMIRALAY_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/themiralay/Proxy-List-World/master/data.txt"),
]
R00TEE_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt"),
    ("socks4", "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt"),
]
IPLOCATE_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt"),
    ("http",   "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt"),
]
SUNNY9577_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt"),
    ("socks4", "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt"),
    ("socks5", "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt"),
]
ALIILAPRO_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt"),
]
DPANGESTUW_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/http_proxies.txt"),
    ("socks4", "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks4_proxies.txt"),
    ("socks5", "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks5_proxies.txt"),
]
ZAEEM20_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt"),
    ("http",   "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt"),
]
ZLOI_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt"),
    ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt"),
    ("socks4", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt"),
]
HOOKZOF_SOURCES: list[tuple[str, str]] = [
    ("socks5", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"),
]
PRXCHK_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt"),
]
SHIFTYTR_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt"),
]
VAKHOV_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt"),
]
MURONGPIG_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http_checked.txt"),
    ("socks5", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5_checked.txt"),
]

_IP_PORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d+")


# ORCHESTRATOR

def load_backfill_pool() -> tuple[list[tuple[str, str]], list[dict]]:
    entries: list[tuple[str, str]] = []
    sources: list[dict]            = []

    _try_source(MONOSANS_URL, load_monosans_proxies, entries, sources)

    for proto, url in ROOSTERKID_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in THESPEEDX_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)
    for proto, url in THEMIRALAY_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in R00TEE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in IPLOCATE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in SUNNY9577_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ALIILAPRO_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in DPANGESTUW_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ZAEEM20_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in ZLOI_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in HOOKZOF_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)

    _try_source(PROXIFLY_URL, _fetch_proxifly, entries, sources)
    for proto, url in JETKAI_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)
    for proto, url in PRXCHK_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in SHIFTYTR_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in VAKHOV_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)
    for proto, url in MURONGPIG_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)

    return _merge_dedup(entries), sources


# FUNCTIONS

def _fetch_proxifly() -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]
    return fetch_with_retry(_do)


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, line.strip()) for line in resp.text.splitlines() if line.strip()]
    return fetch_with_retry(_do)


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, m.group()) for line in resp.text.splitlines()
                for m in (_IP_PORT_RE.search(line),) if m]
    return fetch_with_retry(_do)


def _try_source(url: str, fn, entries: list, sources: list) -> None:
    try:
        result = fn()
        entries.extend(result)
        sources.append({"url": url, "ok": True, "count": len(result)})
    except Exception as exc:
        sources.append({"url": url, "ok": False, "count": 0, "error": type(exc).__name__})


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen:   set[str]              = set()
    result: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key = proxy_key(proto, host_port)
        if key not in seen:
            seen.add(key)
            result.append((proto, host_port))
    return result
