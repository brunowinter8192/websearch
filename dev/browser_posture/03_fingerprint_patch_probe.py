#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    launch_chrome, stop_chrome, profile_dir, start_probe_server, stop_probe_server,
    inject_before_navigation, read_system_colors, read_screen_window_props,
    wait_for_stable_content, extract_value,
)
from _fingerprint_report import write_report

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

SANNYSOFT_URL = "https://bot.sannysoft.com/"
CREEPJS_URL = "https://abrahamjuliot.github.io/creepjs/"
SANNYSOFT_SETTLE_S = 3.0
CREEPJS_MAX_WAIT_S = 25.0

SCREEN_WINDOW_PATCH = """
(function() {
    // Screen dimensions: 1920x1080 (external Mac monitor)
    Object.defineProperty(screen, 'width', { get: () => 1920 });
    Object.defineProperty(screen, 'height', { get: () => 1080 });
    Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
    Object.defineProperty(screen, 'availHeight', { get: () => 1057 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 30 });
    Object.defineProperty(screen, 'pixelDepth', { get: () => 30 });

    // devicePixelRatio: Retina Mac
    Object.defineProperty(window, 'devicePixelRatio', { get: () => 2 });

    // outerWidth/outerHeight: real browser has toolbar (~85px)
    Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
})();
"""

GETCOMPUTEDSTYLE_PATCH = """
(function() {
    // CSS ActiveText: headless renders rgb(255,0,0) — patch getComputedStyle (#39)
    var _origGCS = window.getComputedStyle;
    window.getComputedStyle = function(element, pseudoElt) {
        var style = _origGCS.apply(this, arguments);
        return new Proxy(style, {
            get: function(target, name) {
                var value = target[name];
                if (name === 'color' && value === 'rgb(255, 0, 0)') {
                    return 'rgb(0, 102, 204)';
                }
                return typeof value === 'function' ? value.bind(target) : value;
            }
        });
    };
})();
"""

VARIANTS = [
    {"slug": "full", "label": "1. full patch set (A+B, today's shape)", "script": SCREEN_WINDOW_PATCH + GETCOMPUTEDSTYLE_PATCH},
    {"slug": "screen_only", "label": "2. without getComputedStyle Proxy (A only)", "script": SCREEN_WINDOW_PATCH},
    {"slug": "style_only", "label": "3. without screen/window overrides (B only)", "script": GETCOMPUTEDSTYLE_PATCH},
    {"slug": "none", "label": "4. no patches (baseline)", "script": ""},
]

HARDCODED_PROPS = {
    "screenWidth": 1920, "screenHeight": 1080, "availWidth": 1920, "availHeight": 1057,
    "colorDepth": 30, "pixelDepth": 30, "devicePixelRatio": 2,
}


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    server, thread, port = start_probe_server()
    artifact_url = _compute_artifact_url(port)
    results = await _check_variants(artifact_url, server, thread)

    orphans = check_orphans()
    report_path = write_report(results, orphans, REPORT_DIR, VARIANTS, HARDCODED_PROPS)
    _print_report(report_path, orphans)


# FUNCTIONS

def _compute_artifact_url(port):
    artifact_url = f"http://127.0.0.1:{port}/artifact"
    return artifact_url


async def _check_variants(artifact_url, server, thread):
    results = {}
    try:
        for variant in VARIANTS:
            print(f"=== {variant['label']} ===", file=sys.stderr)
            results[variant["slug"]] = await run_variant(variant, artifact_url)
        print("=== headless reference (no patches, artifact test only) ===", file=sys.stderr)
        results["headless_reference"] = await run_headless_reference(artifact_url)
    finally:
        stop_probe_server(server, thread)
    return results


def check_orphans() -> list[str]:
    result = subprocess.run(["pgrep", "-fl", "browser-posture-probe"], capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _print_report(report_path, orphans):
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Orphan Chrome processes after run: {len(orphans)}", file=sys.stderr)


async def run_variant(variant: dict, artifact_url: str) -> dict:
    profile = profile_dir(f"fp-{variant['slug']}")
    browser, tab, _, _ = await launch_chrome(profile, headless=False, extra_flags=[], backgrounded=True)
    data = {"label": variant["label"]}
    try:
        await inject_before_navigation(tab, variant["script"])

        print("  artifact page (system colors + screen/window props)", file=sys.stderr)
        await tab.go_to(artifact_url, timeout=15.0)
        data["colors"] = await read_system_colors(tab)
        data["props"] = await read_screen_window_props(tab)

        print("  bot.sannysoft.com", file=sys.stderr)
        await tab.go_to(SANNYSOFT_URL, timeout=20.0)
        await asyncio.sleep(SANNYSOFT_SETTLE_S)
        data["sannysoft"] = await extract_sannysoft(tab)

        print("  creepjs", file=sys.stderr)
        await tab.go_to(CREEPJS_URL, timeout=30.0)
        _, settled = await wait_for_stable_content(
            tab, "document.body.textContent.length", interval=2.0, max_wait=CREEPJS_MAX_WAIT_S
        )
        data["creepjs"] = await extract_creepjs(tab)
        data["creepjs"]["settled"] = settled
    finally:
        await stop_chrome(browser, profile)
    return data


async def run_headless_reference(artifact_url: str) -> dict:
    profile = profile_dir("fp-headless-ref")
    browser, tab, _, _ = await launch_chrome(profile, headless=True, extra_flags=[], backgrounded=False)
    data = {"label": "headless reference (no patches)"}
    try:
        await tab.go_to(artifact_url, timeout=15.0)
        data["colors"] = await read_system_colors(tab)
        data["props"] = await read_screen_window_props(tab)
    finally:
        await stop_chrome(browser, profile)
    return data


async def extract_sannysoft(tab) -> dict:
    raw = await tab.execute_script(
        "return JSON.stringify(Array.from(document.querySelectorAll('tr')).map(function(tr) {"
        "var tds = tr.querySelectorAll('td');"
        "if (tds.length < 2) return null;"
        "return {label: tds[0].textContent.trim().slice(0,60), "
        "result: tds[1].textContent.trim().slice(0,80), "
        "failed: /failed/i.test(tds[1].className)};"
        "}).filter(function(r) { return r; }))"
    )
    value = extract_value(raw)
    rows = json.loads(value) if value else []
    failed_rows = [r for r in rows if r["failed"]]
    return {"total_rows": len(rows), "failed_rows": failed_rows, "rows": rows}


async def extract_creepjs(tab) -> dict:
    raw = await tab.execute_script("return document.body.textContent")
    full = extract_value(raw) or ""
    headless_signals = re.findall(r"(\d+)% (like headless|headless|stealth)", full)
    confidence_signals = re.findall(r"confidence: (\w+)", full)
    literal_lie_or_trust = bool(re.search(r"\blie(s|d)?\b|trust score", full, re.IGNORECASE))
    return {
        "body_text_len": len(full),
        "headless_signals": headless_signals,
        "confidence_signals": confidence_signals,
        "literal_lie_or_trust_wording_found": literal_lie_or_trust,
        "raw_excerpt": full[:1500],
    }


if __name__ == "__main__":
    asyncio.run(run_probe())
