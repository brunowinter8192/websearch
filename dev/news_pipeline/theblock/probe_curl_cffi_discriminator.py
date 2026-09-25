#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cffi_requests

PROXIES_JSON   = Path("dev/news_pipeline/theblock/monosans_out_neutral/proxies.json")
TARGET_PRIMARY = "https://www.theblock.co/sitemap_tbco_post_type_post_0.xml"
TARGET_SECONDARY = "https://www.theblock.co/sitemap_tbco_index.xml"
CONCURRENCY    = 20
TIMEOUT        = 15
REPORT_DIR     = Path("dev/news_pipeline/theblock/probe_curl_cffi_discriminator_reports")

XML_MARKERS    = [b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>"]


# ORCHESTRATOR

def probe_curl_cffi_discriminator_workflow():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    _print_loading_proxy_pool()
    proxies = load_proxies()
    _print_pool_summary(proxies)
    _print_primary_header()
    start = time.time()
    primary_results = run_checks(proxies, TARGET_PRIMARY)
    elapsed_primary = _compute_elapsed_primary(start)
    _print_done_in_s(elapsed_primary)

    passing_proxies = _compute_passing_proxies(proxies, primary_results)

    secondary_results, elapsed_secondary = _run_secondary_probe(passing_proxies)

    report_path = _compute_report_path(ts)
    report = build_report(proxies, primary_results, passing_proxies, secondary_results,
                          elapsed_primary, elapsed_secondary, ts)
    report_path.write_text(report)
    _print_report(report_path)


# FUNCTIONS

def _print_loading_proxy_pool():
    print(f"Loading proxy pool from {PROXIES_JSON} ...")


def load_proxies():
    return json.loads(PROXIES_JSON.read_text())


def _print_pool_summary(proxies):
    print(f"Pool: {len(proxies)} proxies (http {sum(1 for p in proxies if p['protocol']=='http')}, "
          f"socks4 {sum(1 for p in proxies if p['protocol']=='socks4')}, "
          f"socks5 {sum(1 for p in proxies if p['protocol']=='socks5')})")


def _print_primary_header():
    print(f"\n=== PRIMARY: {TARGET_PRIMARY} ===")
    print(f"Concurrency {CONCURRENCY}, timeout {TIMEOUT}s ...")


def _compute_elapsed_primary(start):
    elapsed_primary = time.time() - start
    return elapsed_primary


def _print_done_in_s(elapsed_primary):
    print(f"Done in {elapsed_primary:.0f}s")


def _compute_passing_proxies(proxies, primary_results):
    passing_proxies = [p for p, r in zip(proxies, primary_results) if r[0] == "pass"]
    return passing_proxies


def _run_secondary_probe(passing_proxies):
    secondary_results = []
    if passing_proxies:
        _print_secondary_passing_proxies(passing_proxies)
        start2 = time.time()
        secondary_results = run_checks(passing_proxies, TARGET_SECONDARY)
        elapsed_secondary = _compute_elapsed_secondary(start2)
        _print_secondary_elapsed(elapsed_secondary)
    else:
        print("\nNo passing proxies on primary — skipping secondary target.")
        elapsed_secondary = 0.0
    return secondary_results, elapsed_secondary


def _compute_report_path(ts):
    report_path = REPORT_DIR / f"discriminator_{ts}.md"
    return report_path


def build_report(proxies, primary_results, passing_proxies, secondary_results,
                 elapsed_primary, elapsed_secondary, ts):
    total = len(proxies)
    primary_counts = Counter(r[0] for r in primary_results)
    pass_count = primary_counts.get("pass", 0)

    cf_block, conn_err, timeout, other_http = failure_mode_counts(primary_counts)

    lines = []
    lines += build_header_lines(total)
    lines += build_primary_lines(total, primary_counts, pass_count, elapsed_primary,
                                 cf_block, conn_err, timeout, other_http)
    lines += build_passing_lines(passing_proxies)
    lines += build_secondary_lines(passing_proxies, secondary_results, elapsed_secondary)
    lines += build_asn_lines(proxies, passing_proxies)
    lines += build_verdict_lines(pass_count, cf_block, conn_err, timeout)

    return "\n".join(lines) + "\n"


def _print_report(report_path):
    print(f"\nReport: {report_path}")


def run_checks(entries, target):
    results = [None] * len(entries)
    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(check_one, e, target): i
                   for i, e in enumerate(entries)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                results[idx] = (f"fail_unexpected:{type(e).__name__}", -1)
            done += 1
            if done % 50 == 0 or done == len(entries):
                sys.stdout.write(f"\r  {done}/{len(entries)} checked  ")
                sys.stdout.flush()
    print()
    return results


def _print_secondary_passing_proxies(passing_proxies):
    print(f"\n=== SECONDARY: {TARGET_SECONDARY} ({len(passing_proxies)} passing proxies) ===")


def _compute_elapsed_secondary(start2):
    elapsed_secondary = time.time() - start2
    return elapsed_secondary


def _print_secondary_elapsed(elapsed_secondary):
    print(f"Done in {elapsed_secondary:.0f}s")


def failure_mode_counts(primary_counts):
    cf_block   = primary_counts.get("fail_403", 0) + primary_counts.get("fail_429", 0)
    conn_err   = sum(v for k, v in primary_counts.items()
                     if "connection" in k or "ssl" in k or "curl_" in k)
    timeout    = primary_counts.get("fail_timeout", 0)
    other_http = sum(v for k, v in primary_counts.items()
                     if k.startswith("fail_http_") or k == "fail_200_not_xml")
    return cf_block, conn_err, timeout, other_http


def build_header_lines(total):
    lines = []
    lines.append("# theblock.co curl_cffi-chrome Discriminator Run")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Pool source: `{PROXIES_JSON}` ({total} proxies)")
    lines.append(f"Primary target: `{TARGET_PRIMARY}`")
    lines.append(f"Secondary target: `{TARGET_SECONDARY}` (tested on passing proxies only)")
    lines.append(f"Concurrency: {CONCURRENCY}, timeout: {TIMEOUT}s/request")
    return lines


def build_primary_lines(total, primary_counts, pass_count, elapsed_primary,
                        cf_block, conn_err, timeout, other_http):
    lines = []
    lines.append("\n---")
    primary_label = TARGET_PRIMARY.split("/")[-1]
    lines.append(f"\n## Primary Results — `{primary_label}`")
    lines.append(f"\nWall-clock: **{elapsed_primary:.0f}s**")
    lines.append(f"\n| result | count | % |")
    lines.append("|----|----|----|")
    for label, count in sorted(primary_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {label} | {count} | {count/total*100:.1f}% |")

    lines.append(f"\n**PASSING (200 + XML):** {pass_count} / {total}")
    lines.append(f"\n**Failure mode summary:**")
    lines.append(f"| category | count |")
    lines.append("|---|---|")
    lines.append(f"| CF-block (403+429) | {cf_block} |")
    lines.append(f"| connection errors (refused/reset/SSL) | {conn_err} |")
    lines.append(f"| timeout | {timeout} |")
    lines.append(f"| other HTTP | {other_http} |")
    return lines


def build_passing_lines(passing_proxies):
    lines = []
    if passing_proxies:
        lines.append("\n### Passing Proxies")
        lines.append(f"\n{len(passing_proxies)} proxies returned HTTP 200 + XML content:\n")
        for p in passing_proxies:
            asn_org = p.get("asn", {}).get("autonomous_system_organization", "unknown")
            country = p.get("geolocation", {}).get("country", {}).get("iso_code", "??")
            lines.append(f"- `{proxy_url(p)}` — {asn_org} ({country})")
    return lines


def build_secondary_lines(passing_proxies, secondary_results, elapsed_secondary):
    lines = []
    lines.append("\n---")
    lines.append("\n## Secondary Results — `sitemap_tbco_index.xml`")
    if secondary_results:
        sec_counts = Counter(r[0] for r in secondary_results)
        sec_pass = sec_counts.get("pass", 0)
        lines.append(f"\nTested {len(passing_proxies)} proxies that passed primary. Wall-clock: {elapsed_secondary:.0f}s")
        lines.append(f"\n| result | count |")
        lines.append("|---|---|")
        for label, count in sorted(sec_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {label} | {count} |")
        lines.append(f"\nIndex pass: {sec_pass} / {len(passing_proxies)}")
    else:
        lines.append("\nNot run (no proxies passed primary target).")
    return lines


def build_asn_lines(proxies, passing_proxies):
    passing_asns = Counter(
        p["asn"]["autonomous_system_organization"]
        for p in passing_proxies
        if p.get("asn")
    ) if passing_proxies else Counter()

    pool_asns = Counter(
        p["asn"]["autonomous_system_organization"]
        for p in proxies
        if p.get("asn")
    ).most_common(10)

    lines = []
    lines.append("\n---")
    lines.append("\n## ASN Context")
    lines.append("\n### Full pool ASN distribution (top 10 — confirming datacenter composition)")
    lines.append("\n| ASN org | count |")
    lines.append("|---|---|")
    for org, count in pool_asns:
        lines.append(f"| {org} | {count} |")

    if passing_asns:
        lines.append("\n### Passing proxy ASN distribution")
        lines.append("\n| ASN org | count |")
        lines.append("|---|---|")
        for org, count in passing_asns.most_common():
            lines.append(f"| {org} | {count} |")
    return lines


def build_verdict_lines(pass_count, cf_block, conn_err, timeout):
    if pass_count > 0:
        verdict = "(a) — SIGNATURE was the blocker. curl_cffi-chrome passes; free proxy loop is viable."
    elif cf_block > (conn_err + timeout) * 2:
        verdict = "(b) — IP REPUTATION. Failures dominated by 403/429 CF blocks (not connection errors). curl_cffi cannot fix reputation blocks. Free approach DEAD => residential required."
    elif (conn_err + timeout) > cf_block * 2:
        verdict = "(c) — STALE POOL inconclusive. Failures dominated by connection errors/timeouts (proxy IPs dead), not CF responses. Cannot distinguish (a) from (b) without a fresher/larger pool."
    else:
        verdict = "(b/c ambiguous) — Mixed failure modes; neither CF-block nor stale-proxy clearly dominant."

    lines = []
    lines.append("\n---")
    lines.append("\n## Verdict")
    lines.append(f"\n**{verdict}**")
    return lines


def check_one(entry, target):
    purl = proxy_url(entry)
    proxies_dict = {"http": purl, "https": purl}
    try:
        s = cffi_requests.Session(impersonate="chrome")
        r = s.get(target, proxies=proxies_dict, timeout=TIMEOUT)
        s.close()
        return classify_response(r)
    except Exception as e:
        return classify_exception(e)


def proxy_url(entry):
    return f"{entry['protocol']}://{entry['host']}:{entry['port']}"


def classify_response(r):
    if r.status_code == 200:
        content = r.content[:500]
        if any(m in content for m in XML_MARKERS):
            return ("pass", 200)
        return ("fail_200_not_xml", 200)
    elif r.status_code == 403:
        return ("fail_403", 403)
    elif r.status_code == 429:
        return ("fail_429", 429)
    else:
        return (f"fail_http_{r.status_code}", r.status_code)


def classify_exception(e):
    code = getattr(e, "code", None)
    if code is not None:
        code_int = int(code)
        if code_int == 28:
            return ("fail_timeout", code_int)
        elif code_int in (7, 5, 97):
            return ("fail_connection", code_int)
        elif code_int == 6:
            return ("fail_connection", code_int)
        elif code_int in (35, 51, 58, 60):
            return ("fail_ssl", code_int)
        elif code_int in (55, 56):
            return ("fail_connection", code_int)
        else:
            return (f"fail_curl_{code_int}", code_int)
    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return ("fail_timeout", -1)
    return ("fail_connection", -1)


if __name__ == "__main__":
    probe_curl_cffi_discriminator_workflow()
