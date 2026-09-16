#!/usr/bin/env python3
"""Runs `crawl4ai.deep_crawling.BFSDeepCrawlStrategy` for real against books.toscrape.com (a
static, stable scraping-practice site) to verify — by executing, not by reading the source — the
one assumption the whole link-graph-traversal redesign rests on: that `resume_state` can
pre-populate the BFS frontier with an arbitrary URL set instead of a single `start_url`.

Four small, real runs, each capped to a handful of requests:
  1. existence + start_url fate — does resume_state's "pending" set actually get crawled, and
     what happens to start_url when resume_state is also supplied?
  2. resume_state dict shape — minimal correct shape, a wrong key name, and an empty dict.
  3. depth bookkeeping — does an explicit "depths" entry gate max_depth for an injected URL the
     same way it would for a discovered link, and what depth does an UNSTAMPED injected URL get
     by default?
  4. FilterChain bypass — does an injected seed skip the filter chain the way a depth-0 start_url
     does, while a link discovered FROM that seed (to the same host) still gets filtered?

Every run cancels itself (via on_state_change + strategy.cancel()) right after the single seed's
first level is processed, so depth/filter experiments never actually fetch the discovered
next-level URLs — only their PRESENCE in the captured state is inspected.
"""
# INFRASTRUCTURE
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, FilterChain, URLPatternFilter

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

HOMEPAGE = "https://books.toscrape.com/index.html"
TRAVEL_URL = "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
MYSTERY_URL = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
PHILOSOPHY_URL = "https://books.toscrape.com/catalogue/category/books/philosophy_7/index.html"


# ORCHESTRATOR

# Run all four resume_state experiments against one crawler instance, then write the md report
async def url_discovery_probe_workflow() -> None:
    browser_config = BrowserConfig(headless=True, verbose=False)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        exp1 = await run_experiment_1_existence_and_start_url(crawler)
        print(f"[1/4] existence + start_url fate: {exp1['total_results']} results", file=sys.stderr)
        exp2 = await run_experiment_2_dict_shape(crawler)
        print("[2/4] resume_state dict shape: 3 subtests done", file=sys.stderr)
        exp3 = await run_experiment_3_depth_bookkeeping(crawler)
        print("[3/4] depth bookkeeping: 2 variants done", file=sys.stderr)
        exp4 = await run_experiment_4_filter_chain_bypass(crawler)
        print("[4/4] FilterChain bypass: done", file=sys.stderr)

    report_path = write_report(exp1, exp2, exp3, exp4)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

# Standard CrawlerRunConfig wiring a given strategy into batch (non-streaming) mode
def _run_config(strategy: BFSDeepCrawlStrategy) -> CrawlerRunConfig:
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        deep_crawl_strategy=strategy,
        stream=False,
        verbose=False,
    )


# Flatten a CrawlResult list into plain dicts (url, success, status_code, depth) for the report
def _result_rows(results) -> list:
    rows = []
    for r in results:
        rows.append({
            "url": r.url,
            "success": bool(r.success),
            "status_code": getattr(r, "status_code", None),
            "depth": (r.metadata or {}).get("depth") if hasattr(r, "metadata") else None,
        })
    return rows


# on_state_change callback that captures the post-link-discovery state, then cancels the
# strategy so the next BFS level (the discovered children) is never actually fetched
def _capture_and_stop_callback(holder: dict):
    async def callback(state: dict) -> None:
        holder["state"] = state
        holder["strategy"].cancel()
    return callback


# Q1 + Q3: does resume_state's "pending" set get crawled, and is start_url crawled/ignored/collided?
async def run_experiment_1_existence_and_start_url(crawler: AsyncWebCrawler) -> dict:
    pending_urls = [TRAVEL_URL, MYSTERY_URL, PHILOSOPHY_URL]
    resume_state = {"pending": [{"url": u, "parent_url": None} for u in pending_urls]}
    strategy = BFSDeepCrawlStrategy(max_depth=0, resume_state=resume_state)
    results = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy))
    rows = _result_rows(results)
    crawled = {row["url"] for row in rows}
    return {
        "start_url": HOMEPAGE,
        "pending_urls": pending_urls,
        "results": rows,
        "total_results": len(rows),
        "all_pending_crawled": all(u in crawled for u in pending_urls),
        "start_url_crawled": HOMEPAGE in crawled,
    }


# Q2: exact required resume_state shape — minimal-correct, wrong-key, and empty-dict subtests
async def run_experiment_2_dict_shape(crawler: AsyncWebCrawler) -> dict:
    # 2a: minimal correct shape — only "pending", no "visited"/"depths"/"pages_crawled"
    strategy_a = BFSDeepCrawlStrategy(
        max_depth=0,
        resume_state={"pending": [{"url": TRAVEL_URL, "parent_url": None}]},
    )
    results_a = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy_a))

    # 2b: wrong key name ("seed_urls" instead of "pending") — dict is truthy, so resume mode
    # is entered, but .get("pending", []) finds nothing
    strategy_b = BFSDeepCrawlStrategy(
        max_depth=0,
        resume_state={"seed_urls": [TRAVEL_URL]},
    )
    results_b = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy_b))

    # 2c: empty dict — falsy in Python, so `if self._resume_state:` takes the FALSE branch
    strategy_c = BFSDeepCrawlStrategy(max_depth=0, resume_state={})
    results_c = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy_c))

    return {
        "minimal_correct": {"resume_state": {"pending": [{"url": TRAVEL_URL, "parent_url": None}]},
                             "results": _result_rows(results_a)},
        "wrong_key": {"resume_state": {"seed_urls": [TRAVEL_URL]},
                      "results": _result_rows(results_b)},
        "empty_dict": {"resume_state": {}, "results": _result_rows(results_c)},
    }


# Q4: does an explicit "depths" entry gate max_depth for an injected URL, and what depth does an
# unstamped injected URL default to?
async def run_experiment_3_depth_bookkeeping(crawler: AsyncWebCrawler) -> dict:
    # Variant A: seeded at depth=2, max_depth=2 -> next_depth (3) > max_depth -> no children
    holder_a: dict = {}
    strategy_a = BFSDeepCrawlStrategy(
        max_depth=2,
        resume_state={
            "pending": [{"url": MYSTERY_URL, "parent_url": None}],
            "depths": {MYSTERY_URL: 2},
        },
        on_state_change=_capture_and_stop_callback(holder_a),
    )
    holder_a["strategy"] = strategy_a
    results_a = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy_a))
    pending_a = holder_a.get("state", {}).get("pending", [])

    # Variant B: no "depths" entry -> defaults to 0, max_depth=2 -> next_depth (1) <= max_depth -> children discovered
    holder_b: dict = {}
    strategy_b = BFSDeepCrawlStrategy(
        max_depth=2,
        resume_state={"pending": [{"url": MYSTERY_URL, "parent_url": None}]},
        on_state_change=_capture_and_stop_callback(holder_b),
    )
    holder_b["strategy"] = strategy_b
    results_b = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy_b))
    state_b = holder_b.get("state", {})
    pending_b = state_b.get("pending", [])
    child_depths_b = state_b.get("depths", {})
    sample_child_depth = next(iter(child_depths_b.values())) if child_depths_b else None

    return {
        "variant_a_seeded_depth_2": {
            "seeded_depth": 2, "max_depth": 2,
            "seed_result": _result_rows(results_a),
            "children_discovered_count": len(pending_a),
        },
        "variant_b_depth_omitted": {
            "seeded_depth": None, "max_depth": 2,
            "seed_result": _result_rows(results_b),
            "children_discovered_count": len(pending_b),
            "sample_child_depth": sample_child_depth,
        },
    }


# Q5: does an injected seed bypass the FilterChain the way a depth-0 start_url does, while a
# link discovered FROM it (to the same URL, via the sidebar's self-link) still gets filtered?
async def run_experiment_4_filter_chain_bypass(crawler: AsyncWebCrawler) -> dict:
    holder: dict = {}
    filter_chain = FilterChain([URLPatternFilter(patterns="*philosophy_7*", reverse=True)])
    strategy = BFSDeepCrawlStrategy(
        max_depth=1,
        filter_chain=filter_chain,
        resume_state={"pending": [{"url": PHILOSOPHY_URL, "parent_url": None}]},
        on_state_change=_capture_and_stop_callback(holder),
    )
    holder["strategy"] = strategy
    results = await crawler.arun(url=HOMEPAGE, config=_run_config(strategy))
    state = holder.get("state", {})
    children = [item["url"] for item in state.get("pending", [])]

    return {
        "seed_url": PHILOSOPHY_URL,
        "blocking_pattern": "*philosophy_7* (reverse=True, so any URL containing philosophy_7 is rejected)",
        "seed_result": _result_rows(results),
        "children_discovered_count": len(children),
        "philosophy_self_link_in_children": PHILOSOPHY_URL in children,
        "filter_stats": {
            "total": filter_chain.stats.total_urls,
            "passed": filter_chain.stats.passed_urls,
            "rejected": filter_chain.stats.rejected_urls,
        },
    }


# Render every experiment's measured numbers plus the five answers into one timestamped md report
def write_report(exp1: dict, exp2: dict, exp3: dict, exp4: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"01_resume_state_probe_report_{ts}.md"

    lines = [f"# resume_state probe ({ts})", "",
             "Target: books.toscrape.com (static, stable). crawl4ai 0.9.2.", ""]
    lines += _format_experiment_1_section(exp1)
    lines += _format_experiment_2_section(exp2)
    lines += _format_experiment_3_section(exp3)
    lines += _format_experiment_4_section(exp4)

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _format_experiment_1_section(exp1: dict) -> list:
    lines = ["## Experiment 1 — existence + start_url fate", "",
             f"- start_url: `{exp1['start_url']}`",
             f"- resume_state pending ({len(exp1['pending_urls'])}): "
             f"{', '.join(exp1['pending_urls'])}",
             f"- max_depth=0 (isolates: exactly {len(exp1['pending_urls'])} requests if start_url ignored)",
             f"- total results returned: {exp1['total_results']}",
             f"- all 3 pending URLs crawled: {exp1['all_pending_crawled']}",
             f"- start_url crawled too: {exp1['start_url_crawled']}", ""]
    for row in exp1["results"]:
        lines.append(f"  - `{row['url']}` success={row['success']} status={row['status_code']} depth={row['depth']}")
    lines.append("")
    return lines


def _format_experiment_2_section(exp2: dict) -> list:
    lines = ["## Experiment 2 — resume_state dict shape", ""]
    for key, label in [("minimal_correct", "2a. minimal correct: {\"pending\": [{url, parent_url}]}, no other keys"),
                        ("wrong_key", "2b. wrong key: {\"seed_urls\": [...]} (dict truthy, \"pending\" missing)"),
                        ("empty_dict", "2c. empty dict: {} (falsy -> falls back to plain start_url crawl)")]:
        sub = exp2[key]
        lines.append(f"### {label}")
        lines.append(f"- resume_state: `{sub['resume_state']}`")
        lines.append(f"- results returned: {len(sub['results'])}")
        for row in sub["results"]:
            lines.append(f"  - `{row['url']}` success={row['success']} status={row['status_code']} depth={row['depth']}")
        lines.append("")
    return lines


def _format_experiment_3_section(exp3: dict) -> list:
    lines = ["## Experiment 3 — depth bookkeeping vs max_depth", ""]
    va = exp3["variant_a_seeded_depth_2"]
    lines += [f"### Variant A — depths={{{MYSTERY_URL}: 2}}, max_depth=2",
              f"- seed fetched: {va['seed_result']}",
              f"- children discovered (next BFS level size): {va['children_discovered_count']}",
              "- expectation: next_depth=3 > max_depth=2 -> 0 children", ""]
    vb = exp3["variant_b_depth_omitted"]
    lines += [f"### Variant B — depths omitted (defaults to 0), max_depth=2",
              f"- seed fetched: {vb['seed_result']}",
              f"- children discovered (next BFS level size): {vb['children_discovered_count']}",
              f"- sample assigned child depth: {vb['sample_child_depth']}",
              "- expectation: next_depth=1 <= max_depth=2 -> children discovered, each stamped depth=1", ""]
    return lines


def _format_experiment_4_section(exp4: dict) -> list:
    return ["## Experiment 4 — FilterChain bypass for the injected seed", "",
            f"- seed: `{exp4['seed_url']}`",
            f"- filter: {exp4['blocking_pattern']}",
            f"- seed fetch result: {exp4['seed_result']}",
            f"- children discovered: {exp4['children_discovered_count']}",
            f"- philosophy_7 self-link present among children: {exp4['philosophy_self_link_in_children']}",
            f"- filter_chain.stats: total={exp4['filter_stats']['total']} "
            f"passed={exp4['filter_stats']['passed']} rejected={exp4['filter_stats']['rejected']}",
            "- expectation: seed fetched despite matching the blocking pattern (seeds bypass "
            "can_process_url entirely); the SAME URL, rediscovered as a child via the sidebar's "
            "self-link, gets rejected by the filter chain (rejected count >= 1).", ""]


if __name__ == "__main__":
    asyncio.run(url_discovery_probe_workflow())
