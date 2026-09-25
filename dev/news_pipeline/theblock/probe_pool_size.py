#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

SCRIPT_DIR  = Path(__file__).parent
REPORTS_DIR = SCRIPT_DIR / "probe_pool_size_reports"

TIMEOUT_S      = 15.0
SEMAPHORE_SIZE = 20

BASELINE_RAW = 17_202

HTTP_SOURCES: list[tuple[str, bool]] = [
    ("https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=http",   False),
    ("https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=https",  False),
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",               False),
    ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",   False),
    ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",  False),
    ("https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",         False),
    ("https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",       False),
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",                False),
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",               False),
    ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",                  False),
    ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",                 False),
    ("https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",          False),
    ("https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",         False),
    ("https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt",       False),
    ("https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/http_proxies.txt",        False),
    ("https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt",                   False),
    ("https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",                      False),
    ("https://raw.githubusercontent.com/mzyui/proxy-list/main/http.txt",                     False),
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",          False),
    ("https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",        False),
    ("https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",       False),
    ("https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",   False),
    ("https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt",  False),
    ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",   False),
    ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",  False),
    ("https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",                  False),
    ("https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",               False),
    ("https://raw.githubusercontent.com/themiralay/Proxy-List-World/master/data.txt",        True),
    ("https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",      True),
]

SOCKS4_SOURCES: list[tuple[str, bool]] = [
    ("https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks4",          False),
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",                      False),
    ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt", False),
    ("https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",                False),
    ("https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt", False),
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",                       False),
    ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt",                         False),
    ("https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",                 False),
    ("https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks4.txt",              False),
    ("https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks4_proxies.txt",               False),
    ("https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt",                           False),
    ("https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt",                             False),
    ("https://raw.githubusercontent.com/mzyui/proxy-list/main/socks4.txt",                            False),
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",                 False),
    ("https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",               False),
    ("https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt",          False),
    ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt", False),
    ("https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",                         False),
    ("https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt",                      False),
]

SOCKS5_SOURCES: list[tuple[str, bool]] = [
    ("https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks5",          False),
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",                      False),
    ("https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",                        False),
    ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt", False),
    ("https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",                False),
    ("https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt", False),
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",                       False),
    ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",                         False),
    ("https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",                 False),
    ("https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks5.txt",              False),
    ("https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks5_proxies.txt",               False),
    ("https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt",                           False),
    ("https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",                             False),
    ("https://raw.githubusercontent.com/mzyui/proxy-list/main/socks5.txt",                            False),
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",                 False),
    ("https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",               False),
    ("https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",          False),
    ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt", False),
    ("https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",                         False),
    ("https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",                      False),
]

_PROXY_RE = re.compile(r'^([a-zA-Z0-9.\-]+):(\d{1,5})(?=[:\s]|$)')


# ORCHESTRATOR

async def probe_pool_size_workflow() -> None:
    ts_start = datetime.now(timezone.utc)
    t0 = time.monotonic()

    print(f"=== proxy pool size probe | {ts_start.strftime('%Y-%m-%dT%H:%M:%SZ')} ===")
    print(f"Fetching {len(HTTP_SOURCES) + len(SOCKS4_SOURCES) + len(SOCKS5_SOURCES)} sources "
          f"(semaphore={SEMAPHORE_SIZE}, timeout={TIMEOUT_S}s) ...")

    results = await fetch_all_sources()
    elapsed = time.monotonic() - t0

    stats   = compute_stats(results)
    md_text = build_report_md(results, stats, ts_start, elapsed)
    print_console_summary(results, stats, ts_start, elapsed)
    write_report(md_text, ts_start)


# FUNCTIONS

async def fetch_all_sources() -> list[dict]:
    tasks: list[tuple[str, str, bool]] = (
        [(u, "http",   m) for u, m in HTTP_SOURCES]
        + [(u, "socks4", m) for u, m in SOCKS4_SOURCES]
        + [(u, "socks5", m) for u, m in SOCKS5_SOURCES]
    )
    sem = asyncio.Semaphore(SEMAPHORE_SIZE)
    async with httpx.AsyncClient() as client:
        return list(await asyncio.gather(
            *[fetch_source(client, sem, url, bucket, mixed) for url, bucket, mixed in tasks]
        ))


def compute_stats(results: list[dict]) -> dict:
    buckets: dict[str, dict] = {
        "http":   {"raw": 0, "proxies": set()},
        "socks4": {"raw": 0, "proxies": set()},
        "socks5": {"raw": 0, "proxies": set()},
    }
    global_proxies: set[str] = set()

    for r in results:
        b = buckets[r["bucket"]]
        b["raw"] += r["raw_count"]
        b["proxies"].update(r["proxies"])
        global_proxies.update(r["proxies"])

    total_raw            = sum(b["raw"] for b in buckets.values())
    global_unique        = len(global_proxies)
    sum_bucket_uniques   = sum(len(b["proxies"]) for b in buckets.values())
    bucket_overlap       = sum_bucket_uniques - global_unique

    return {
        "buckets":            {k: {"raw": v["raw"], "unique": len(v["proxies"])} for k, v in buckets.items()},
        "total_raw":          total_raw,
        "global_unique":      global_unique,
        "sum_bucket_uniques": sum_bucket_uniques,
        "bucket_overlap":     bucket_overlap,
        "failed":             [r for r in results if not r["ok"]],
        "ok_count":           sum(1 for r in results if r["ok"]),
    }


def build_report_md(results: list[dict], stats: dict, ts: datetime, elapsed: float) -> str:
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = []
    lines += _render_header(results, stats, ts_str, elapsed)
    lines += _render_headline(stats)
    lines += _render_bucket_summary(results, stats)
    lines += _render_source_detail(results)
    lines += _render_failed_sources(stats)
    lines += _render_baseline_comparison(stats)

    return "\n".join(lines)


def print_console_summary(results: list[dict], stats: dict, ts: datetime, elapsed: float) -> None:
    print(f"\nDone in {elapsed:.1f}s | OK: {stats['ok_count']}/{len(results)}")
    print("\n--- Per-bucket ---")
    for bucket in ("http", "socks4", "socks5"):
        b = stats["buckets"][bucket]
        print(f"  {bucket:<8}  raw={b['raw']:>8,}  unique={b['unique']:>8,}")
    print("\n--- Headline ---")
    print(f"  Total raw:              {stats['total_raw']:>10,}")
    print(f"  Global unique:          {stats['global_unique']:>10,}")
    print(f"  Sum per-bucket uniques: {stats['sum_bucket_uniques']:>10,}")
    print(f"  Cross-bucket overlap:   {stats['bucket_overlap']:>10,}")
    print(f"  vs baseline (~{BASELINE_RAW:,}):    {stats['total_raw'] / BASELINE_RAW:.1f}× raw")
    if stats["failed"]:
        print(f"\n  Failed sources ({len(stats['failed'])}):")
        for r in stats["failed"]:
            print(f"    {r['url']}  →  {r['error']}")


def write_report(md_text: str, ts: datetime) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fname = REPORTS_DIR / f"pool_size_{ts.strftime('%Y%m%dT%H%M%SZ')}.md"
    fname.write_text(md_text, encoding="utf-8")
    print(f"\nReport: {fname}")


async def fetch_source(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    url: str,
    bucket: str,
    is_mixed: bool,
) -> dict:
    async with sem:
        try:
            r = await client.get(url, timeout=TIMEOUT_S, follow_redirects=True)
            status = r.status_code
            if status != 200:
                return _dead(url, bucket, is_mixed, status, f"HTTP {status}")
            raw_count = 0
            proxies: set[str] = set()
            for line in r.text.splitlines():
                p = parse_proxy_line(line)
                if p:
                    raw_count += 1
                    proxies.add(p)
            return {
                "url": url, "bucket": bucket, "mixed": is_mixed,
                "ok": True, "status": status, "error": None,
                "raw_count": raw_count, "proxies": proxies,
            }
        except httpx.TimeoutException:
            return _dead(url, bucket, is_mixed, None, "timeout")
        except Exception as e:
            return _dead(url, bucket, is_mixed, None, str(e)[:100])


def _render_header(results: list[dict], stats: dict, ts_str: str, elapsed: float) -> list:
    return [
        f"# Proxy Pool Size — {ts_str}",
        "",
        f"**Wall-clock:** {elapsed:.1f}s  |  **Sources:** {len(results)}  |  "
        f"**OK:** {stats['ok_count']}  |  **Failed:** {len(stats['failed'])}",
        "",
    ]


def _render_headline(stats: dict) -> list:
    return [
        "## Headline",
        "",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Total raw (all sources, incl. duplicates) | **{stats['total_raw']:,}** |",
        f"| Total unique — global host:port dedup | **{stats['global_unique']:,}** |",
        f"| Sum of per-bucket uniques (http+socks4+socks5) | **{stats['sum_bucket_uniques']:,}** |",
        f"| Cross-protocol bucket overlap | **{stats['bucket_overlap']:,}** |",
        f"| Baseline (monosans single-source, OldThemes 16) | ~17,202 raw |",
        f"| Raw vs baseline | **{stats['total_raw'] / BASELINE_RAW:.1f}×** |",
        "",
    ]


def _render_bucket_summary(results: list[dict], stats: dict) -> list:
    lines = ["## Per-Protocol Bucket Summary", ""]
    lines += ["| Bucket | Sources | Raw | Unique |", "|---|---|---|---|"]
    for bucket in ("http", "socks4", "socks5"):
        b     = stats["buckets"][bucket]
        count = sum(1 for r in results if r["bucket"] == bucket)
        lines.append(f"| {bucket} | {count} | {b['raw']:,} | {b['unique']:,} |")
    lines.append("")
    return lines


def _render_source_detail(results: list[dict]) -> list:
    lines: list[str] = []
    for bucket in ("http", "socks4", "socks5"):
        bucket_results = [r for r in results if r["bucket"] == bucket]
        lines += [f"## Source Detail — {bucket}", ""]
        lines += ["| Source | Status | Raw count | Note |", "|---|---|---|---|"]
        for r in bucket_results:
            label  = _source_label(r["url"])
            status = str(r["status"]) if r["status"] else "—"
            if r["ok"]:
                note = "mixed (protocol-unknown)" if r["mixed"] else ""
                lines.append(f"| `{label}` | {status} | {r['raw_count']:,} | {note} |")
            else:
                lines.append(f"| `{label}` | FAIL | 0 | {r['error']} |")
        lines.append("")
    return lines


def _render_failed_sources(stats: dict) -> list:
    if stats["failed"]:
        lines = ["## Failed Sources", ""]
        for r in stats["failed"]:
            lines.append(f"- `{r['url']}`  →  {r['error']}")
        lines.append("")
        return lines
    return ["## Failed Sources", "", "None.", ""]


def _render_baseline_comparison(stats: dict) -> list:
    return [
        "## Baseline Comparison",
        "",
        f"Previous baseline (monosans single-source, OldThemes 16): **~{BASELINE_RAW:,} raw** proxies.",
        f"This run — 68 sources: **{stats['total_raw']:,} raw** / **{stats['global_unique']:,} unique**.",
        f"Raw pool expansion: **{stats['total_raw'] / BASELINE_RAW:.1f}×** vs baseline.",
        f"Global unique is {stats['global_unique'] / BASELINE_RAW:.1f}× the old raw count "
        f"(which was itself un-deduped).",
        "",
    ]


def _dead(url: str, bucket: str, is_mixed: bool, status, error: str) -> dict:
    return {
        "url": url, "bucket": bucket, "mixed": is_mixed,
        "ok": False, "status": status, "error": error,
        "raw_count": 0, "proxies": set(),
    }


def parse_proxy_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if '://' in line:
        line = line.split('://', 1)[1]
    if '@' in line:
        line = line.rsplit('@', 1)[1]
    m = _PROXY_RE.match(line)
    if m and 1 <= int(m.group(2)) <= 65535:
        return f"{m.group(1)}:{m.group(2)}"
    return None


def _source_label(url: str) -> str:
    if "proxyscrape.com" in url:
        proto = url.split("protocol=")[-1]
        return f"proxyscrape/{proto}"
    parts = url.rstrip("/").split("/")
    return "/".join(parts[-3:]) if len(parts) >= 3 else url


if __name__ == "__main__":
    asyncio.run(probe_pool_size_workflow())
