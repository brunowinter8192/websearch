# INFRASTRUCTURE
import sys
import os
import argparse
import json
from datetime import datetime, timezone
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from curated_sources import load_curated_proxies

from curl_cffi import requests as cffi

THEBLOCK_URL = "https://www.theblock.co/sitemap_tbco_index.xml"
XML_MARKERS = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")
TIMEOUT = 15
REPORT_DIR = Path(__file__).parent / "probe_curated_theblock_cf_reports"

# ORCHESTRATOR

def probe_curated_theblock_cf_workflow(concurrency: int) -> None:
    proxies = load_curated_proxies()
    proto_counts = Counter(p for p, _ in proxies)
    print(f"Loaded {len(proxies)} proxies — http:{proto_counts['http']} "
          f"socks4:{proto_counts['socks4']} socks5:{proto_counts['socks5']}")

    results = run_checks(proxies, concurrency)
    report_path = write_report(proxies, results, proto_counts, concurrency)
    print(f"Report: {report_path}")


# FUNCTIONS

def check_proxy(protocol: str, host_port: str) -> bool:
    purl = f"{protocol}://{host_port}"
    try:
        s = cffi.Session(impersonate="chrome")
        r = s.get(THEBLOCK_URL, proxies={"http": purl, "https": purl}, timeout=TIMEOUT)
        head = r.content[:500]
        return r.status_code == 200 and any(m in head for m in XML_MARKERS)
    except Exception:
        return False


def run_checks(proxies: list, concurrency: int) -> list:
    results = []
    total = len(proxies)
    done = 0
    passed = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(check_proxy, proto, hp): (proto, hp) for proto, hp in proxies}
        for fut in as_completed(futures):
            proto, hp = futures[fut]
            ok = fut.result()
            results.append((proto, hp, ok))
            done += 1
            if ok:
                passed += 1
                print(f"  PASS [{done}/{total}] {proto}://{hp}")
            elif done % 200 == 0:
                print(f"  ... {done}/{total} checked, {passed} passed so far")

    return results


def write_report(proxies: list, results: list, proto_counts: Counter, concurrency: int) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"curated_theblock_cf_{ts}.md"

    passers = [(proto, hp) for proto, hp, ok in results if ok]
    total = len(results)
    total_passed = len(passers)

    lines = build_config_and_results_lines(ts, concurrency, total, total_passed)
    lines += build_protocol_lines(results, proto_counts)
    lines += build_passing_lines(passers, total_passed)
    lines += build_comparison_lines(total, total_passed)

    path.write_text("\n".join(lines) + "\n")
    return path


def build_config_and_results_lines(ts: str, concurrency: int, total: int, total_passed: int) -> list[str]:
    return [
        f"# Curated theblock CF-pass probe — {ts}",
        "",
        "## Run config",
        f"- List: monosans+proxifly curated (load_curated_proxies)",
        f"- Check: curl_cffi chrome impersonation → {THEBLOCK_URL}",
        f"- Pass criterion: status 200 + XML marker in first 500 bytes",
        f"- Timeout: {TIMEOUT}s per proxy",
        f"- Concurrency: {concurrency} threads (ThreadPoolExecutor)",
        f"- No alive pre-filter — direct CF gate",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total proxies | {total} |",
        f"| Passed CF gate | {total_passed} |",
        f"| Failed | {total - total_passed} |",
        f"| Overall pass rate | {total_passed/total*100:.3f}% |",
    ]


def build_protocol_lines(results: list, proto_counts: Counter) -> list[str]:
    proto_pass = Counter(proto for proto, _, ok in results if ok)
    proto_fail = Counter(proto for proto, _, ok in results if not ok)

    lines = [
        "",
        "## Per-protocol breakdown",
        "",
        "| Protocol | In list | Passed | Failed | Pass rate |",
        "|---|---|---|---|---|",
    ]
    for proto in ("http", "socks4", "socks5"):
        n_in = proto_counts[proto]
        n_pass = proto_pass[proto]
        n_fail = proto_fail[proto]
        rate = f"{n_pass/n_in*100:.3f}%" if n_in else "—"
        lines.append(f"| {proto} | {n_in} | {n_pass} | {n_fail} | {rate} |")
    return lines


def build_passing_lines(passers: list, total_passed: int) -> list[str]:
    lines = [
        "",
        "## Passing proxies",
        "",
        f"Total: {total_passed}",
        "",
    ]
    if passers:
        lines.append("| Protocol | Proxy |")
        lines.append("|---|---|")
        for proto, hp in passers:
            lines.append(f"| {proto} | {hp} |")
    else:
        lines.append("None.")
    return lines


def build_comparison_lines(total: int, total_passed: int) -> list[str]:
    return [
        "",
        "## Comparison",
        "",
        f"jhao104 Stage 2 (http-only, scraped sources): 1/1177 = 0.085%",
        f"Curated (this run, all protocols): {total_passed}/{total} = {total_passed/total*100:.3f}%",
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curated list direct theblock CF-pass probe")
    parser.add_argument("--concurrency", type=int, default=128,
                        help="ThreadPoolExecutor max_workers (default: 128)")
    args = parser.parse_args()
    probe_curated_theblock_cf_workflow(args.concurrency)
