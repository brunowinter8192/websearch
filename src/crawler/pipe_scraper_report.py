# INFRASTRUCTURE
from pathlib import Path
from urllib.parse import urlparse

from src.crawler.pipe_scraper_acquisition import onward_link_identity


# FUNCTIONS

def domain_from_urls(urls: list[str]) -> str:
    if not urls:
        return 'unknown'
    return urlparse(urls[0]).netloc.replace('.', '_')

def write_tmp_report(domain: str, results: list[dict]) -> None:
    path = Path(f"/tmp/{domain}_scrape_report.md")
    lines = [
        f"# Scrape Report — {domain}",
        "",
        f"Total: {len(results)} URLs",
        "",
        "| status | bytes | wall_ms | url |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.get('status_code') or '-'} | {r['bytes']} | {r['wall_ms']} | {r['url']} |"
        )
    path.write_text('\n'.join(lines), encoding='utf-8')

def collect_onward_links(urls: list[str], results: list[dict], engine: str) -> list[str] | None:
    if engine == "camoufox":
        return None
    already_known = {onward_link_identity(u) for u in urls}
    already_known.discard(None)
    seen = set(already_known)
    onward = []
    for r in results:
        for link in r.get('links', []):
            if link in seen:
                continue
            seen.add(link)
            onward.append(link)
    return onward

def write_onward_links_file(domain: str, onward_links: list[str] | None) -> None:
    if onward_links is None:
        return
    path = Path(f"/tmp/{domain}_scrape_links.txt")
    path.write_text(("\n".join(onward_links) + "\n") if onward_links else "", encoding='utf-8')

def print_summary(results: list[dict], wall_s: float, onward_links: list[str] | None) -> None:
    total = len(results)
    status_counts: dict = {}
    for r in results:
        key = r['status_code'] if r['status_code'] is not None else 'no_status'
        status_counts[key] = status_counts.get(key, 0) + 1
    status_str = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items(), key=lambda kv: str(kv[0])))
    zero_bytes = sum(1 for r in results if r['bytes'] == 0)
    links_str = ("onward links not collected (camoufox engine)" if onward_links is None
                 else f"{len(onward_links)} onward links collected")
    print(f"Scraped {total} URLs in {wall_s:.0f}s — status: {status_str} — "
          f"{zero_bytes} returned 0 bytes — {links_str}")
