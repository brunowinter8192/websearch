# INFRASTRUCTURE
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

FETCH_TIMEOUT = 15.0

MONOSANS_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"

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

JETKAI_SOURCES: list[tuple[str, str]] = [
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"),
    ("http",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt"),
    ("socks4", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt"),
    ("socks5", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt"),
]

_IP_PORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d+")
_BACKOFF    = (1, 2, 4, 8)
COOLDOWN_S  = 3600


# FUNCTIONS

def load_backfill_pool() -> tuple[list[tuple[str, str]], list[dict]]:
    entries: list[tuple[str, str]] = []
    sources: list[dict]            = []

    _try_source(MONOSANS_URL, _load_monosans, entries, sources)
    _try_roosterkid_sources(entries, sources)
    _try_databay_sources(entries, sources)
    _try_thespeedx_sources(entries, sources)
    _try_themiralay_sources(entries, sources)
    _try_r00tee_sources(entries, sources)
    _try_iplocate_sources(entries, sources)
    _try_sunny9577_sources(entries, sources)
    _try_aliilapro_sources(entries, sources)
    _try_dpangestuw_sources(entries, sources)
    _try_zaeem20_sources(entries, sources)
    _try_zloi_sources(entries, sources)
    _try_hookzof_sources(entries, sources)

    return _merge_dedup(entries), sources


class PersistentCooldownManager:

    def __init__(self, cooldown_s: int = COOLDOWN_S):
        self._cooldown_td   = timedelta(seconds=cooldown_s)
        self._burned_utc: dict[str, datetime] = {}

    def mark_burned(self, proto: str, host_port: str) -> None:
        self._burned_utc[proxy_key(proto, host_port)] = datetime.now(timezone.utc)

    def is_eligible(self, proto: str, host_port: str) -> bool:
        burned_at = self._burned_utc.get(proxy_key(proto, host_port))
        if burned_at is None:
            return True
        return (datetime.now(timezone.utc) - burned_at) >= self._cooldown_td

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]

    def cooldown_count(self) -> int:
        now = datetime.now(timezone.utc)
        return sum(1 for dt in self._burned_utc.values() if (now - dt) < self._cooldown_td)


def _load_monosans() -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(MONOSANS_URL, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()
        entries = []
        for entry in raw:
            proto = entry["protocol"]
            host  = entry["host"]
            port  = entry["port"]
            user  = entry.get("username")
            pw    = entry.get("password")
            hp    = f"{user}:{pw}@{host}:{port}" if (user and pw) else f"{host}:{port}"
            entries.append((proto, hp))
        return entries
    return fetch_with_retry(_do)


def _try_roosterkid_sources(entries, sources):
    for proto, url in ROOSTERKID_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_databay_sources(entries, sources):
    for proto, url in DATABAY_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)


def _try_thespeedx_sources(entries, sources):
    for proto, url in THESPEEDX_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_bare_txt(p, u), entries, sources)


def _try_themiralay_sources(entries, sources):
    for proto, url in THEMIRALAY_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_r00tee_sources(entries, sources):
    for proto, url in R00TEE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_iplocate_sources(entries, sources):
    for proto, url in IPLOCATE_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_sunny9577_sources(entries, sources):
    for proto, url in SUNNY9577_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_aliilapro_sources(entries, sources):
    for proto, url in ALIILAPRO_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_dpangestuw_sources(entries, sources):
    for proto, url in DPANGESTUW_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_zaeem20_sources(entries, sources):
    for proto, url in ZAEEM20_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_zloi_sources(entries, sources):
    for proto, url in ZLOI_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _try_hookzof_sources(entries, sources):
    for proto, url in HOOKZOF_SOURCES:
        _try_source(url, lambda p=proto, u=url: _fetch_roosterkid(p, u), entries, sources)


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen:   set[str]               = set()
    result: list[tuple[str, str]]  = []
    for proto, hp in entries:
        key = proxy_key(proto, hp)
        if key not in seen:
            seen.add(key)
            result.append((proto, hp))
    return result


def _try_source(url: str, fn, entries: list, sources: list) -> None:
    try:
        result = fn()
        entries.extend(result)
        sources.append({"url": url, "ok": True, "count": len(result)})
    except Exception:
        sources.append({"url": url, "ok": False, "count": 0})


def proxy_key(proto: str, host_port: str) -> str:
    clean        = host_port.split("@")[-1]
    host, port_s = clean.rsplit(":", 1)
    return f"{proto}://{host}:{int(port_s)}"


def _fetch_roosterkid(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, m.group()) for ln in resp.text.splitlines()
                for m in (_IP_PORT_RE.search(ln),) if m]
    return fetch_with_retry(_do)


def _fetch_bare_txt(proto: str, url: str) -> list[tuple[str, str]]:
    def _do():
        resp = httpx.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return [(proto, ln.strip()) for ln in resp.text.splitlines() if ln.strip()]
    return fetch_with_retry(_do)


def fetch_with_retry(fn):
    last_exc = None
    for delay in (None, *_BACKOFF):
        if delay is not None:
            time.sleep(delay)
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
    raise last_exc
