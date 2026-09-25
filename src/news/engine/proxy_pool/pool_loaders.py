# INFRASTRUCTURE

import re

import httpx

from src.config import PROXY_LIST_FETCH_TIMEOUT
from src.news.engine.proxy_pool.monosans_loader import load_monosans_proxies, MONOSANS_URL
from src.news.engine.proxy_pool.pool_retry import fetch_with_retry
from src.news.engine.proxy_pool.proxy_key import proxy_key

PROXIFLY_URL = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"

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
    entries, sources = _collect_sources()
    return _merge_dedup(entries), sources


# FUNCTIONS

def _collect_sources() -> tuple[list[tuple[str, str]], list[dict]]:
    entries: list[tuple[str, str]] = []
    sources: list[dict]            = []

    _try_source(MONOSANS_URL, load_monosans_proxies, entries, sources)

    _try_roosterkid_sources(ROOSTERKID_SOURCES, entries, sources)
    _try_bare_txt_sources(THESPEEDX_SOURCES, entries, sources)
    _try_roosterkid_sources(THEMIRALAY_SOURCES, entries, sources)
    _try_roosterkid_sources(R00TEE_SOURCES, entries, sources)
    _try_roosterkid_sources(IPLOCATE_SOURCES, entries, sources)
    _try_roosterkid_sources(SUNNY9577_SOURCES, entries, sources)
    _try_roosterkid_sources(ALIILAPRO_SOURCES, entries, sources)
    _try_roosterkid_sources(DPANGESTUW_SOURCES, entries, sources)
    _try_roosterkid_sources(ZAEEM20_SOURCES, entries, sources)
    _try_roosterkid_sources(ZLOI_SOURCES, entries, sources)
    _try_roosterkid_sources(HOOKZOF_SOURCES, entries, sources)

    _try_source(PROXIFLY_URL, _fetch_proxifly, entries, sources)
    _try_bare_txt_sources(JETKAI_SOURCES, entries, sources)
    _try_roosterkid_sources(PRXCHK_SOURCES, entries, sources)
    _try_roosterkid_sources(SHIFTYTR_SOURCES, entries, sources)
    _try_roosterkid_sources(VAKHOV_SOURCES, entries, sources)
    _try_roosterkid_sources(MURONGPIG_SOURCES, entries, sources)

    return entries, sources


def _try_source(url: str, fn, entries: list, sources: list) -> None:
    try:
        result = fn()
        entries.extend(result)
        sources.append({"url": url, "ok": True, "count": len(result)})
    except Exception as exc:
        sources.append({"url": url, "ok": False, "count": 0, "error": type(exc).__name__})


def _try_roosterkid_sources(source_list: list[tuple[str, str]], entries: list, sources: list) -> None:
    for proto, url in source_list:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=PROXY_LIST_FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, m.group()) for line in resp.text.splitlines()
                for m in (_IP_PORT_RE.search(line),) if m]
    return fetch_with_retry(_do)


def _try_bare_txt_sources(source_list: list[tuple[str, str]], entries: list, sources: list) -> None:
    for proto, url in source_list:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=PROXY_LIST_FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, line.strip()) for line in resp.text.splitlines() if line.strip()]
    return fetch_with_retry(_do)


def _fetch_proxifly() -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(PROXIFLY_URL, timeout=PROXY_LIST_FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]
    return fetch_with_retry(_do)


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen:   set[str]              = set()
    result: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key = proxy_key(proto, host_port)
        if key not in seen:
            seen.add(key)
            result.append((proto, host_port))
    return result
