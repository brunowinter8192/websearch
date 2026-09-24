#!/usr/bin/env python3

# INFRASTRUCTURE

import re
import httpx

from monosans_loader import load_monosans_proxies
from proxy_status_log import proxy_key

PROXIFLY_URL      = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
FETCH_TIMEOUT     = 15.0

THESPEEDX_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
]
DATABAY_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt"),
    ("socks4", "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks5.txt"),
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

_IP_PORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d+")

# ORCHESTRATOR

def load_curated_proxies() -> list[tuple[str, str]]:
    monosans = load_monosans_proxies()
    proxifly = _fetch_proxifly()
    return _merge_dedup(monosans + proxifly)


def load_thespeedx_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in THESPEEDX_SOURCES:
        entries.extend(_fetch_bare_txt(proto, url))
    return _merge_dedup(entries)


def load_databay_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in DATABAY_SOURCES:
        entries.extend(_fetch_bare_txt(proto, url))
    return _merge_dedup(entries)


def load_jetkai_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in JETKAI_SOURCES:
        entries.extend(_fetch_bare_txt(proto, url))
    return _merge_dedup(entries)


def load_roosterkid_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in ROOSTERKID_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_themiralay_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in THEMIRALAY_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_r00tee_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in R00TEE_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_iplocate_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in IPLOCATE_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_sunny9577_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in SUNNY9577_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_aliilapro_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in ALIILAPRO_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_dpangestuw_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in DPANGESTUW_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_zaeem20_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in ZAEEM20_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_zloi_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in ZLOI_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_hookzof_proxies() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for proto, url in HOOKZOF_SOURCES:
        entries.extend(_fetch_roosterkid(proto, url))
    return _merge_dedup(entries)


def load_backfill_pool() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    entries.extend(load_monosans_proxies())
    for loader in [
        load_roosterkid_proxies,  load_databay_proxies,   load_thespeedx_proxies,
        load_themiralay_proxies,  load_r00tee_proxies,    load_iplocate_proxies,
        load_sunny9577_proxies,   load_aliilapro_proxies, load_dpangestuw_proxies,
        load_zaeem20_proxies,     load_zloi_proxies,      load_hookzof_proxies,
    ]:
        entries.extend(loader())
    return _merge_dedup(entries)

# FUNCTIONS

def _fetch_proxifly() -> list[tuple[str, str]]:
    resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    entries: list[tuple[str, str]] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line:
            entries.append((proto, line))
    return entries


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    entries: list[tuple[str, str]] = []
    for line in resp.text.splitlines():
        m = _IP_PORT_RE.search(line)
        if m:
            entries.append((proto, m.group()))
    return entries


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen:   set[str]              = set()
    result: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key = proxy_key(proto, host_port)
        if key not in seen:
            seen.add(key)
            result.append((proto, host_port))
    return result
