# INFRASTRUCTURE
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.search.browser import new_tab, close_browser

SANNYSOFT_URL = "https://bot.sannysoft.com/"
SCREENSHOT_PATH = "/tmp/pydoll_probe_sannysoft.png"

EXTRACT_RESULTS_JS = """
(() => {
    const rows = document.querySelectorAll('table tr');
    const results = [];
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
            const label = cells[0].innerText.trim();
            const value = cells[1].innerText.trim();
            const passed = row.classList.contains('passed');
            const failed = row.classList.contains('failed');
            if (label) {
                results.push({
                    label,
                    value,
                    status: passed ? 'PASS' : (failed ? 'FAIL' : 'UNKNOWN')
                });
            }
        }
    });
    return JSON.stringify(results);
})()
"""

READ_NAVIGATOR_JS = """
(() => {
    const props = {
        webdriver: navigator.webdriver,
        plugins_length: navigator.plugins.length,
        languages: JSON.stringify(navigator.languages),
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory,
        vendor: navigator.vendor,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
    };
    // WebGL renderer
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            const dbgInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (dbgInfo) {
                props.webgl_vendor = gl.getParameter(dbgInfo.UNMASKED_VENDOR_WEBGL);
                props.webgl_renderer = gl.getParameter(dbgInfo.UNMASKED_RENDERER_WEBGL);
            }
        }
    } catch(e) {
        props.webgl_error = String(e);
    }
    // Permissions API: notifications should be 'default' for real user
    return JSON.stringify(props);
})()
"""

CHECK_PERMISSIONS_JS = """
(async () => {
    try {
        const result = await navigator.permissions.query({ name: 'notifications' });
        return result.state;
    } catch(e) {
        return 'error: ' + String(e);
    }
})()
"""


# ORCHESTRATOR

def main():
    asyncio.run(run_probe())


# FUNCTIONS

async def run_probe():
    print(f"[probe] Starting Chrome via browser.py with existing options...")
    tab = await new_tab()
    try:
        print(f"[probe] Navigating to {SANNYSOFT_URL} ...")
        await tab.go_to(SANNYSOFT_URL)

        print("[probe] Waiting 4s for JS detection checks to settle...")
        await asyncio.sleep(4)

        print(f"[probe] Taking screenshot → {SCREENSHOT_PATH}")
        await tab.take_screenshot(SCREENSHOT_PATH)
        print(f"[probe] Screenshot saved.")

        table_results, nav_props, perm_state = await _read_probe_data(tab)

        passed, failed, unknown = _print_results_table(table_results)
        _print_navigator_reads(nav_props, perm_state)
        _print_key_signals(nav_props, perm_state, failed)
        _print_json_summary(passed, failed, unknown, table_results, nav_props, perm_state)

    finally:
        await close_browser()


async def _read_probe_data(tab) -> tuple[list, dict, str]:
    print("[probe] Extracting sannysoft result table...")
    raw_table = await tab.execute_script(EXTRACT_RESULTS_JS)
    table_json = _extract_value(raw_table)
    table_results = json.loads(table_json) if table_json else []

    print("[probe] Reading navigator properties...")
    raw_nav = await tab.execute_script(READ_NAVIGATOR_JS)
    nav_json = _extract_value(raw_nav)
    nav_props = json.loads(nav_json) if nav_json else {}

    print("[probe] Checking permissions API...")
    raw_perm = await tab.execute_script(CHECK_PERMISSIONS_JS, await_promise=True)
    perm_state = _extract_value(raw_perm) or "error"
    return table_results, nav_props, perm_state


def _print_results_table(table_results: list) -> tuple[list, list, list]:
    print("\n" + "="*60)
    print("SANNYSOFT BOT CHECK — RESULTS TABLE")
    print("="*60)
    passed = [r for r in table_results if r['status'] == 'PASS']
    failed = [r for r in table_results if r['status'] == 'FAIL']
    unknown = [r for r in table_results if r['status'] == 'UNKNOWN']
    print(f"  PASS: {len(passed)} | FAIL: {len(failed)} | UNKNOWN: {len(unknown)}\n")
    for r in table_results:
        marker = "PASS" if r['status'] == 'PASS' else ("FAIL" if r['status'] == 'FAIL' else "UNKNOWN")
        print(f"  {marker} {r['label']}: {r['value']}")
    return passed, failed, unknown


def _print_navigator_reads(nav_props: dict, perm_state: str) -> None:
    print("\n" + "="*60)
    print("DIRECT NAVIGATOR / WEBGL READS")
    print("="*60)
    for k, v in nav_props.items():
        print(f"  {k}: {v}")
    print(f"  permissions.notifications: {perm_state}")


def _print_key_signals(nav_props: dict, perm_state: str, failed: list) -> None:
    print("\n" + "="*60)
    print("KEY SIGNALS (SUMMARY)")
    print("="*60)
    webdriver_val = nav_props.get('webdriver')
    print(f"  navigator.webdriver   = {webdriver_val!r}  {'OK undefined/false' if not webdriver_val else 'FAIL TRUE — bot flagged'}")
    print(f"  navigator.plugins     = {nav_props.get('plugins_length')} entries  {'OK' if nav_props.get('plugins_length', 0) > 0 else 'FAIL 0 — headless tell'}")
    wgl = nav_props.get('webgl_renderer', '')
    swiftshader = 'SwiftShader' in str(wgl) or 'llvmpipe' in str(wgl).lower()
    print(f"  webgl_renderer        = {wgl!r}  {'FAIL SwiftShader — headless GPU' if swiftshader else 'OK'}")
    perm_ok = 'default' in str(perm_state)
    print(f"  notifications perm    = {perm_state!r}  {'OK' if perm_ok else 'FAIL not default — headless tell'}")
    print(f"  navigator.languages   = {nav_props.get('languages')}")
    fail_labels = [r['label'] for r in failed]
    print(f"\n  FAILED CHECKS: {fail_labels}")
    print(f"  Screenshot: {SCREENSHOT_PATH}")


def _print_json_summary(passed: list, failed: list, unknown: list, table_results: list, nav_props: dict, perm_state: str) -> None:
    summary = {
        "passed_count": len(passed),
        "failed_count": len(failed),
        "unknown_count": len(unknown),
        "table_results": table_results,
        "navigator": nav_props,
        "permissions_notifications": perm_state,
    }
    print("\nJSON_SUMMARY_START")
    print(json.dumps(summary, indent=2))
    print("JSON_SUMMARY_END")


def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError) as exc:
        print(f"extract_value: dropped {type(exc).__name__} for result {str(result)[:200]}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
