# INFRASTRUCTURE
import importlib.metadata
from datetime import datetime
from pathlib import Path

ROUTE_STAGES = ["self_launch", "cdp_port_wait", "cdp_connect_page_navigate", "teardown"]
REFERENCE_STAGE = "reference_launch"


# FUNCTIONS

def pct(count: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{round(100 * count / total)}%"


def diff_cmdlines(self_cmdline: list[str] | None, reference_cmdline: list[str] | None) -> dict:
    if not self_cmdline or not reference_cmdline:
        return {"comparable": False}

    def flag_set(cmdline):
        return {a.split("=")[0] if a.startswith("--") else a for a in cmdline[1:]}

    self_flags = flag_set(self_cmdline)
    ref_flags = flag_set(reference_cmdline)
    return {
        "comparable": True,
        "only_in_reference": sorted(ref_flags - self_flags),
        "only_in_self": sorted(self_flags - ref_flags),
        "common_count": len(self_flags & ref_flags),
    }


def stage_focus_breakdown(focus_samples: list[tuple[str, str]]) -> list[tuple[str, int, int]]:
    totals: dict[str, int] = {s: 0 for s in [*ROUTE_STAGES, REFERENCE_STAGE]}
    chrome_counts: dict[str, int] = {s: 0 for s in [*ROUTE_STAGES, REFERENCE_STAGE]}
    for stage_name, app in focus_samples:
        totals.setdefault(stage_name, 0)
        chrome_counts.setdefault(stage_name, 0)
        totals[stage_name] += 1
        if "chrome" in app.lower():
            chrome_counts[stage_name] += 1
    order = [*ROUTE_STAGES, REFERENCE_STAGE]
    order += [s for s in totals if s not in order]
    return [(s, totals[s], chrome_counts[s]) for s in order]


def _build_self_launch_section(self_launch_result: dict, cdp_http_check: dict) -> list[str]:
    return [
        "## 1. Self-launch + CDP endpoint",
        "",
        f"- `open -g -n -a` launch issued: {self_launch_result['launched']}",
        f"- Error (if any): {self_launch_result['error'] or 'none'}",
        f"- CDP HTTP `/json/version` reachable: {cdp_http_check['ready']}",
        f"- Detail: {cdp_http_check['detail']}",
    ]


def _build_scrape_section(scrape_result: dict) -> list[str]:
    return [
        "",
        "## 2. crawl4ai connect + scrape over cdp_url",
        "",
        "Config shape used: `BrowserConfig(cdp_url=f\"http://127.0.0.1:{port}\", "
        "browser_mode=\"custom\", enable_stealth=True, cdp_cleanup_on_close=True)` + "
        "`UndetectedAdapter()` + `AsyncPlaywrightCrawlerStrategy`. `headless` field is DEAD on this "
        "path (never read inside `browser_manager.py`'s `cdp_url` branch — confirmed by reading the "
        "source, not just inferred) — headed-ness comes entirely from how we spawned the process.",
        "",
        f"- Scrape success: {scrape_result['success']}",
        f"- Content length: {scrape_result['content_len']}",
        f"- Error (if any): {scrape_result['error'] or 'none'}",
    ]


def _build_focus_poll_section(focus_samples: list[tuple[str, str]]) -> list[str]:
    stage_breakdown = stage_focus_breakdown(focus_samples)
    route_apps = [app for stage_name, app in focus_samples if stage_name in ROUTE_STAGES]
    route_total = len(route_apps)
    route_chrome = sum(1 for app in route_apps if "chrome" in app.lower())

    lines = [
        "",
        "## 3. Focus poll (whole sequence: self-launch -> connect -> page creation -> navigation -> teardown)",
        "",
        "**Headline figure is the ROUTE UNDER TEST ONLY** (`self_launch` + `cdp_port_wait` + "
        "`cdp_connect_page_navigate` + `teardown`) — EXCLUDES `reference_launch`, which is this "
        "script's own internal tooling step (a direct, un-backgrounded patchright launch captured "
        "only for the cmdline diff in section 4, not part of the cdp_url route and not expected to "
        "avoid focus steal — folding it into the headline would misrepresent the route being tested):",
        "",
        f"- Route samples: {route_total}",
        f"- Route Chrome-frontmost count: {route_chrome} ({pct(route_chrome, route_total)})",
        f"- Distinct apps seen (whole run, all stages): {sorted({app for _, app in focus_samples})}",
        "",
        "**Per-stage breakdown** (attributes any Chrome-frontmost hit to WHICH step caused it — "
        "`cdp_connect_page_navigate` bundles connect/`get_page()`/goto, the page-creation-over-CDP "
        "moment playwright#42343 flags; finer sub-staging inside it would require hooking crawl4ai "
        "internals, out of scope here). A stage showing 0 samples means it completed faster than "
        "the 0.25s poll interval — NOT that it was confirmed focus-clean, just unsampled. Table "
        "order is thematic (route stages grouped first), NOT chronological — `reference_launch` "
        "actually runs FIRST in real execution, before any route stage:",
        "",
        "| Stage | in route? | samples | chrome frontmost | % |",
        "|-------|-----------|---------|-------------------|---|",
    ]
    for stage_name, total, chrome_count in stage_breakdown:
        in_route = "yes" if stage_name in ROUTE_STAGES else "NO (reference/tooling)"
        lines.append(f"| {stage_name} | {in_route} | {total} | {chrome_count} | {pct(chrome_count, total)} |")
    return lines


def _build_cmdline_delta_section(reference: dict, self_cmdline: list[str] | None, cmdline_diff: dict) -> list[str]:
    lines = [
        "",
        "## 4. cmdline delta vs. patchright reference (headed, probe 04 Run B shape)",
        "",
        f"- Reference launch error: {reference['error'] or 'none'}",
        f"- Reference PID/exe: {reference['pid']} / `{reference['exe']}`",
        f"- Self-launch cmdline captured: {self_cmdline is not None}",
    ]
    if cmdline_diff.get("comparable"):
        lines += [
            f"- Flags common to both: {cmdline_diff['common_count']}",
            f"- **Only in reference (patchright-owned surface we would NOT get on this route):** "
            f"{cmdline_diff['only_in_reference']}",
            f"- Only in self-launch (ours, not patchright's): {cmdline_diff['only_in_self']}",
        ]
    else:
        lines.append("- Not comparable — one of the two cmdlines was not captured.")
    return lines


def _build_teardown_section(orphans: list[str]) -> list[str]:
    lines = [
        "",
        "## Teardown",
        "",
        f"Orphan processes/launchd jobs after the full probe: {len(orphans)}",
    ]
    if orphans:
        lines.append("")
        lines.extend(f"    {o}" for o in orphans)
    return lines


def write_report(
    bundle_path: Path, reference: dict, self_launch_result: dict, cdp_http_check: dict,
    scrape_result: dict, self_cmdline: list[str] | None, cmdline_diff: dict,
    focus_samples: list[tuple[str, str]], orphans: list[str], report_dir: Path,
) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"05_cdp_headed_probe_{ts}.md"
    crawl4ai_version = importlib.metadata.version("crawl4ai")
    patchright_version = importlib.metadata.version("patchright")

    lines = [
        f"# CDP Headed Probe (Milestone 1b) — {ts}",
        "",
        f"Dev-only probe (macOS). `crawl4ai=={crawl4ai_version}`, `patchright=={patchright_version}`. "
        f"Bundle: `{bundle_path}`.",
        "",
    ]
    lines += _build_self_launch_section(self_launch_result, cdp_http_check)
    lines += _build_scrape_section(scrape_result)
    lines += _build_focus_poll_section(focus_samples)
    lines += _build_cmdline_delta_section(reference, self_cmdline, cmdline_diff)
    lines += _build_teardown_section(orphans)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
