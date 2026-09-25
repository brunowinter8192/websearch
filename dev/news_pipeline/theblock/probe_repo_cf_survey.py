# INFRASTRUCTURE
import sys
import asyncio
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from curl_cffi import requests as cffi

sys.path.insert(0, str(Path(__file__).parent))
from probe_pool_size import HTTP_SOURCES, SOCKS4_SOURCES, SOCKS5_SOURCES

THEBLOCK_URL  = "https://www.theblock.co/sitemap_tbco_index.xml"
XML_MARKERS   = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")
CHECK_TIMEOUT = 15
REJECTIONS = Counter()
SAMPLE_SIZE   = 1250
CONCURRENCY   = 50
FETCH_TIMEOUT = 15.0
REPORT_DIR    = Path(__file__).parent / "probe_repo_cf_survey_reports"

import re
_PROXY_RE = re.compile(r'^([a-zA-Z0-9.\-]+):(\d{1,5})(?=[:\s]|$)')


# ORCHESTRATOR

def probe_repo_cf_survey_workflow() -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = _compute_report_path(ts)

    repo_groups = build_repo_groups()
    _print_repos_to_survey(repo_groups)

    write_report_header(report_path, ts, repo_groups)

    print("\n[1/3] Fetching proxy lists...")
    repo_proxies, failed_sources = asyncio.run(fetch_all_repos(repo_groups))

    _print_failed_sources(failed_sources)
    print("\nRepo unique counts:")
    _print_repo_counts(repo_proxies)

    write_fetch_summary(report_path, repo_proxies, failed_sources)

    _print_check_header()
    repo_results = _check_repos(repo_proxies, report_path)
    _print_rejections()

    print("\n[3/3] Finalising report...")
    finalize_report(report_path, repo_results, repo_proxies)
    _print_report(report_path)


# FUNCTIONS

def _compute_report_path(ts):
    report_path = REPORT_DIR / f"repo_cf_survey_{ts}.md"
    return report_path


def build_repo_groups() -> dict:
    groups: dict[str, list] = defaultdict(list)
    for url, is_mixed in HTTP_SOURCES:
        groups[repo_key_from_url(url)].append(("http", url, is_mixed))
    for url, is_mixed in SOCKS4_SOURCES:
        groups[repo_key_from_url(url)].append(("socks4", url, is_mixed))
    for url, is_mixed in SOCKS5_SOURCES:
        groups[repo_key_from_url(url)].append(("socks5", url, is_mixed))
    return dict(groups)


def _print_repos_to_survey(repo_groups):
    print(f"Repos to survey: {len(repo_groups)}")


def write_report_header(path: Path, ts: str, repo_groups: dict) -> None:
    lines = [
        f"# Per-repo theblock-CF survey — {ts}",
        "",
        f"- Check: curl_cffi chrome → {THEBLOCK_URL}",
        f"- Pass: status 200 + XML marker in first 500B  |  timeout: {CHECK_TIMEOUT}s",
        f"- Sample: {SAMPLE_SIZE} per repo (all if smaller)  |  concurrency: {CONCURRENCY}",
        f"- Repos: {len(repo_groups)}",
        "",
        "---",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


async def fetch_all_repos(repo_groups: dict) -> tuple[dict, list]:
    sem = asyncio.Semaphore(20)
    repo_proxies: dict[str, set] = defaultdict(set)
    failed_sources: list[tuple[str, str, str, str]] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        repo_keys = []
        source_refs = []
        for rk, entries in repo_groups.items():
            for protocol, url, is_mixed in entries:
                tasks.append(fetch_one(client, sem, protocol, url, is_mixed))
                repo_keys.append(rk)
                source_refs.append((protocol, url))
        results = await asyncio.gather(*tasks)
    for rk, (protocol, url), (proxies, error) in zip(repo_keys, source_refs, results):
        repo_proxies[rk].update(proxies)
        if error is not None:
            failed_sources.append((rk, protocol, url, error))
    return dict(repo_proxies), failed_sources


def _print_failed_sources(failed_sources):
    print(f"\nFailed sources: {len(failed_sources)}")


def _print_repo_counts(repo_proxies):
    for rk, proxies in sorted(repo_proxies.items(), key=lambda x: -len(x[1])):
        print(f"  {rk:<30} {len(proxies):>7,}")


def write_fetch_summary(path: Path, repo_proxies: dict, failed_sources: list) -> None:
    lines = [
        "## Fetch summary (unique proxies per repo)",
        "",
        "| Repo | Unique | Protocols |",
        "|---|---|---|",
    ]
    for rk, proxies in sorted(repo_proxies.items(), key=lambda x: -len(x[1])):
        protos = Counter(p for p, _ in proxies)
        proto_str = " ".join(f"{k}:{v}" for k, v in sorted(protos.items()))
        lines.append(f"| {rk} | {len(proxies):,} | {proto_str} |")
    lines += ["", "### Failed sources", ""]
    if failed_sources:
        lines += ["| Repo | Protocol | URL | Error |", "|---|---|---|---|"]
        for rk, protocol, url, error in failed_sources:
            lines.append(f"| {rk} | {protocol} | {url} | {error} |")
    else:
        lines.append("None.")
    lines += ["", "---", ""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _print_check_header():
    print(f"\n[2/3] CF-checking repos (sample={SAMPLE_SIZE}, concurrency={CONCURRENCY})...")


def _check_repos(repo_proxies, report_path):
    repo_results = {}
    for repo_key in sorted(repo_proxies.keys()):
        proxies = list(repo_proxies[repo_key])
        if not proxies:
            print(f"  {repo_key}: 0 proxies — skip")
            continue
        sample = random.sample(proxies, min(len(proxies), SAMPLE_SIZE))
        print(f"  {repo_key}: {len(proxies):,} unique → sampling {len(sample)}", flush=True)
        result = check_repo(repo_key, sample)
        repo_results[repo_key] = result
        write_repo_result(report_path, repo_key, result)
        total = result["sample"]
        passed = result["passed"]
        rate = passed / total * 100 if total else 0
        print(f"    → {passed}/{total} passed ({rate:.2f}%)", flush=True)
    return repo_results


def _print_rejections() -> None:
    print(f"proxy check rejections: {dict(REJECTIONS)}", file=sys.stderr)


def finalize_report(path: Path, repo_results: dict, repo_proxies: dict) -> None:
    ranked = sorted(repo_results.values(), key=lambda x: -x["rate"])

    lines = [
        "---",
        "",
        "## Ranked by CF-rate (descending)",
        "",
        "| Rank | Repo | Total-unique | Sample | Passed | CF-rate | http% | socks4% | socks5% |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(ranked, 1):
        rk = r["repo_key"]
        total_unique = len(repo_proxies.get(rk, set()))
        def prate(proto):
            n = r["proto_total"].get(proto, 0)
            p = r["proto_pass"].get(proto, 0)
            return f"{p/n*100:.2f}%" if n else "—"
        lines.append(
            f"| {i} | {rk} | {total_unique:,} | {r['sample']} | {r['passed']} | "
            f"{r['rate']:.3f}% | {prate('http')} | {prate('socks4')} | {prate('socks5')} |"
        )

    lines += [
        "",
        "## Cumulative unique (top-down by CF-rate)",
        "",
        "| Repos included | Cumulative unique |",
        "|---|---|",
    ]
    seen: set = set()
    for r in ranked:
        rk = r["repo_key"]
        seen.update(repo_proxies.get(rk, set()))
        lines.append(f"| …+{rk} | {len(seen):,} |")

    lines += ["", ""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _print_report(report_path):
    print(f"\nReport: {report_path}")


def repo_key_from_url(url: str) -> str:
    if "proxyscrape.com" in url:
        return "proxyscrape"
    if "raw.githubusercontent.com" in url:
        parts = url.split("/")
        idx = parts.index("raw.githubusercontent.com")
        return f"{parts[idx+1]}/{parts[idx+2]}"
    return url.split("/")[2]


async def fetch_one(client: httpx.AsyncClient, sem: asyncio.Semaphore,
                    protocol: str, url: str, is_mixed: bool) -> tuple[set, str | None]:
    async with sem:
        try:
            r = await client.get(url, timeout=FETCH_TIMEOUT, follow_redirects=True)
            if r.status_code != 200:
                return set(), f"HTTP {r.status_code}"
            result = set()
            for line in r.text.splitlines():
                hp = parse_proxy_line(line)
                if hp:
                    result.add((protocol, hp))
            return result, None
        except Exception as e:
            return set(), f"{type(e).__name__}: {str(e)[:100]}"


def check_repo(repo_key: str, sample: list) -> dict:
    t0 = time.monotonic()
    passed_list = []
    proto_pass = Counter()
    proto_total = Counter()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(check_proxy, proto, hp): (proto, hp) for proto, hp in sample}
        for fut in as_completed(futures):
            proto, hp = futures[fut]
            proto_total[proto] += 1
            if fut.result():
                proto_pass[proto] += 1
                passed_list.append((proto, hp))

    elapsed = time.monotonic() - t0
    total = len(sample)
    passed = len(passed_list)
    return {
        "repo_key":    repo_key,
        "sample":      total,
        "passed":      passed,
        "rate":        passed / total * 100 if total else 0.0,
        "proto_pass":  dict(proto_pass),
        "proto_total": dict(proto_total),
        "passers":     passed_list,
        "elapsed":     elapsed,
    }


def write_repo_result(path: Path, repo_key: str, result: dict) -> None:
    r = result
    lines = [
        f"### {repo_key}",
        "",
        f"sample={r['sample']}  passed={r['passed']}  rate={r['rate']:.3f}%  "
        f"elapsed={r['elapsed']:.0f}s",
        "",
        "| Protocol | Checked | Passed | Rate |",
        "|---|---|---|---|",
    ]
    for proto in ("http", "socks4", "socks5"):
        n = r["proto_total"].get(proto, 0)
        p = r["proto_pass"].get(proto, 0)
        rate = f"{p/n*100:.3f}%" if n else "—"
        lines.append(f"| {proto} | {n} | {p} | {rate} |")
    if r["passers"]:
        lines += ["", "**Passers:**"]
        for proto, hp in r["passers"]:
            lines.append(f"- {proto}://{hp}")
    lines += ["", ""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_proxy_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "://" in line:
        line = line.split("://", 1)[1]
    if "@" in line:
        line = line.rsplit("@", 1)[1]
    m = _PROXY_RE.match(line)
    if m and 1 <= int(m.group(2)) <= 65535:
        return f"{m.group(1)}:{m.group(2)}"
    return None


def check_proxy(protocol: str, host_port: str) -> bool:
    purl = f"{protocol}://{host_port}"
    try:
        s = cffi.Session(impersonate="chrome")
        r = s.get(THEBLOCK_URL, proxies={"http": purl, "https": purl}, timeout=CHECK_TIMEOUT)
        head = r.content[:500]
        return r.status_code == 200 and any(m in head for m in XML_MARKERS)
    except cffi.exceptions.RequestException as exc:
        REJECTIONS[type(exc).__name__] += 1
        return False


if __name__ == "__main__":
    probe_repo_cf_survey_workflow()
