#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ACCEPT_MD = "text/markdown, text/html"
CONCURRENCY = 10
TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (compatible; cf-md-probe/1.0)"

URLS: list[tuple[str, str]] = [
    ("A", "https://blog.cloudflare.com/"),
    ("A", "https://blog.cloudflare.com/markdown-for-agents/"),
    ("A", "https://developers.cloudflare.com/"),
    ("A", "https://developers.cloudflare.com/workers/"),
    ("A", "https://www.cloudflare.com/"),
    ("B", "https://dev.to/"),
    ("B", "https://www.npmjs.com/"),
    ("B", "https://discord.com/blog"),
    ("B", "https://shopify.dev/"),
    ("B", "https://docs.anthropic.com/"),
    ("B", "https://huggingface.co/docs"),
    ("B", "https://vercel.com/docs"),
    ("B", "https://tailwindcss.com/docs"),
    ("B", "https://supabase.com/blog"),
    ("B", "https://fly.io/docs/"),
    ("B", "https://docs.railway.com/"),
    ("B", "https://linear.app/blog"),
    ("B", "https://hashnode.com/"),
    ("B", "https://docs.deno.com/"),
    ("B", "https://docs.astro.build/"),
    ("B", "https://docs.pydantic.dev/"),
    ("B", "https://posthog.com/blog"),
    ("B", "https://render.com/docs"),
    ("B", "https://medium.com/"),
    ("C", "https://en.wikipedia.org/wiki/Web_scraping"),
    ("C", "https://docs.python.org/3/"),
    ("C", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept"),
    ("C", "https://arxiv.org/abs/2301.00001"),
    ("C", "https://raw.githubusercontent.com/vinta/awesome-python/master/README.md"),
]

REPORTS_DIR = Path(__file__).parent / "md"


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe URLs for Cloudflare Markdown-for-Agents (Accept: text/markdown) adoption."
    )
    _add_arguments(parser)
    args = parser.parse_args()
    out = _compute_out(args)
    asyncio.run(cf_md_adoption_workflow(out))


# FUNCTIONS

def _add_arguments(parser):
    parser.add_argument(
        "--output-dir", dest="output_dir", default=None,
        help=f"Report directory (default: {REPORTS_DIR})",
    )


def _compute_out(args):
    out = Path(args.output_dir) if args.output_dir else REPORTS_DIR
    return out


async def cf_md_adoption_workflow(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"cf_md_adoption: probing {len(URLS)} URLs (concurrency={CONCURRENCY})", file=sys.stderr)

    sem = asyncio.Semaphore(CONCURRENCY)
    md_headers = {"Accept": ACCEPT_MD, "User-Agent": USER_AGENT}
    plain_headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(headers=md_headers, follow_redirects=True, timeout=TIMEOUT) as client:
        tasks = [probe_url(client, sem, cat, url) for cat, url in URLS]
        results = await asyncio.gather(*tasks)

    positives = [r for r in results if r["md_served"]]
    if positives:
        print(f"\nFetching HTML baselines for {len(positives)} MD-positive URL(s)…", file=sys.stderr)
        async with httpx.AsyncClient(headers=plain_headers, follow_redirects=True, timeout=TIMEOUT) as client:
            baseline_tasks = [fetch_html_baseline(client, sem, r["url"]) for r in positives]
            html_sizes = await asyncio.gather(*baseline_tasks)
        for r, html_bytes in zip(positives, html_sizes):
            r["html_bytes"] = html_bytes

    end_time = time.time()
    report_path = write_report(results, ts, start_time, end_time, output_dir)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Runtime: {end_time - start_time:.1f}s", file=sys.stderr)


async def probe_url(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, cat: str, url: str
) -> dict:
    async with sem:
        print(f"  [{cat}] {url[:70]}", file=sys.stderr)
        t0 = time.monotonic()
        try:
            resp = await client.get(url)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            ct = resp.headers.get("content-type", "")
            md_served = "text/markdown" in ct
            return {
                "cat": cat,
                "url": url,
                "status": resp.status_code,
                "content_type": ct,
                "md_served": md_served,
                "cf_fronted": "cf-ray" in resp.headers,
                "cf_ray": resp.headers.get("cf-ray", ""),
                "server": resp.headers.get("server", ""),
                "x_md_tokens": resp.headers.get("x-markdown-tokens", ""),
                "resp_bytes": len(resp.content),
                "html_bytes": None,
                "elapsed_ms": elapsed_ms,
                "error": None,
            }
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "cat": cat,
                "url": url,
                "status": None,
                "content_type": "",
                "md_served": False,
                "cf_fronted": False,
                "cf_ray": "",
                "server": "",
                "x_md_tokens": "",
                "resp_bytes": 0,
                "html_bytes": None,
                "elapsed_ms": elapsed_ms,
                "error": str(exc)[:120],
            }


async def fetch_html_baseline(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str
) -> int:
    async with sem:
        resp = await client.get(url)
        return len(resp.content)


def write_report(
    results: list[dict], ts: str, start_time: float, end_time: float, output_dir: Path
) -> Path:
    sections = [
        format_header(results, ts, start_time, end_time),
        format_table(results),
        format_summary(results),
    ]
    report_path = output_dir / f"06_cf_md_adoption_{ts}.md"
    report_path.write_text("\n\n".join(sections), encoding="utf-8")
    return report_path


def format_header(
    results: list[dict], ts: str, start_time: float, end_time: float
) -> str:
    probe_ts = datetime.fromtimestamp(start_time).isoformat(timespec="seconds")
    return (
        f"# Cloudflare Markdown Adoption Probe — {ts}\n\n"
        f"**Probe timestamp:** {probe_ts}  \n"
        f"**URLs probed:** {len(results)}  \n"
        f"**Library:** httpx {httpx.__version__}  \n"
        f"**Concurrency:** {CONCURRENCY} (asyncio.Semaphore)  \n"
        f"**Timeout:** {TIMEOUT}s per request  \n"
        f"**Runtime:** {end_time - start_time:.1f}s  \n"
        f"**Accept header sent:** `{ACCEPT_MD}`"
    )


def format_table(results: list[dict]) -> str:
    lines = [
        "## Per-URL Results\n",
        "| # | Cat | URL | Status | CF | MD | Content-Type | x-md-tokens | HTML-bytes | MD-bytes | Byte-reduction | ms |",
        "|---|-----|-----|--------|----|----|-------------|------------|-----------|---------|---------------|-----|",
    ]
    for i, r in enumerate(results, 1):
        url_s = r["url"][:52] + ("…" if len(r["url"]) > 52 else "")
        cf = "✓" if r["cf_fronted"] else "✗"
        md = "✓" if r["md_served"] else "✗"
        ct_s = r["content_type"].split(";")[0].strip() if r["content_type"] else "—"
        tokens = r["x_md_tokens"] or "—"
        status_s = str(r["status"]) if r["status"] is not None else "ERR"

        if r["md_served"]:
            md_bytes_s = f"{r['resp_bytes']:,}"
            html_bytes_s = f"{r['html_bytes']:,}" if r["html_bytes"] is not None else "—"
            if r["html_bytes"]:
                pct = (1 - r["resp_bytes"] / r["html_bytes"]) * 100
                reduction_s = f"{pct:.1f}%"
            else:
                reduction_s = "—"
        else:
            md_bytes_s = "—"
            html_bytes_s = f"{r['resp_bytes']:,}" if not r["error"] else "—"
            reduction_s = "—"

        lines.append(
            f"| {i} | {r['cat']} | {url_s} | {status_s} | {cf} | {md} "
            f"| {ct_s} | {tokens} | {html_bytes_s} | {md_bytes_s} | {reduction_s} | {r['elapsed_ms']} |"
        )
    return "\n".join(lines)


def format_summary(results: list[dict]) -> str:
    cf_fronted = [r for r in results if r["cf_fronted"]]
    md_served = [r for r in results if r["md_served"]]
    errors = [r for r in results if r["error"]]

    lines = _format_summary_stats(results, cf_fronted, md_served)
    lines += _format_summary_errors(errors)
    lines += _format_summary_positive_urls(md_served)
    lines += _format_summary_server_distribution(cf_fronted)
    return "\n".join(lines)


def _format_summary_stats(results: list[dict], cf_fronted: list[dict], md_served: list[dict]) -> list:
    total = len(results)
    md_among_cf = [r for r in cf_fronted if r["md_served"]]
    reductions = [
        (1 - r["resp_bytes"] / r["html_bytes"]) * 100
        for r in md_served
        if r["html_bytes"] and r["html_bytes"] > 0
    ]

    lines = [
        "## Summary\n",
        f"**CF-fronted (cf-ray seen):** {len(cf_fronted)} / {total}  ",
        f"**Markdown-served:** {len(md_served)} / {total}  ",
        f"**Markdown-served among CF-fronted:** {len(md_among_cf)} / {len(cf_fronted)}  ",
    ]

    if reductions:
        lines += [
            f"**Mean byte-reduction (positive cases):** {statistics.mean(reductions):.1f}%  ",
            f"**Median byte-reduction (positive cases):** {statistics.median(reductions):.1f}%  ",
        ]
    else:
        lines += [
            "**Mean byte-reduction:** — (no positive cases with baseline)  ",
            "**Median byte-reduction:** —  ",
        ]
    return lines


def _format_summary_errors(errors: list[dict]) -> list:
    lines = []
    if errors:
        lines += ["", f"**Request errors:** {len(errors)}  "]
        for r in errors:
            lines.append(f"- `{r['url']}`: {r['error']}  ")
    return lines


def _format_summary_positive_urls(md_served: list[dict]) -> list:
    lines = []
    if md_served:
        lines += ["", "### Positive-Case URLs (for future run comparison)\n"]
        for r in md_served:
            token_note = f" · {r['x_md_tokens']} tokens" if r["x_md_tokens"] else ""
            lines.append(f"- {r['url']}{token_note}  ")
    return lines


def _format_summary_server_distribution(cf_fronted: list[dict]) -> list:
    lines = []
    if cf_fronted:
        server_counts: dict[str, int] = {}
        for r in cf_fronted:
            s = r["server"] or "(none)"
            server_counts[s] = server_counts.get(s, 0) + 1
        lines += ["", "### Server Header Distribution (CF-fronted sites)\n"]
        for s, n in sorted(server_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- `{s}`: {n}  ")
    return lines


if __name__ == "__main__":
    main()
