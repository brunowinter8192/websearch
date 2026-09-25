#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import PageCommands
from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yml"
REPORTS_DIR = SCRIPT_DIR / "md"
PNG_DIR = SCRIPT_DIR / "png"
HTML_DIR = SCRIPT_DIR / "html"
CAPTURE_URL = "https://www.google.com/search?q=test"


# ORCHESTRATOR

async def capture_sorry() -> None:
    cfg = load_config(CONFIG_PATH)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    browser = await start_browser(cfg)
    url, title, html, png_path = await _capture_page(browser, cfg, ts)

    status = _compute_status(url)
    write_outputs(url, title, html, png_path, status, ts)
    _print_status(status, url, title, png_path, ts)


# FUNCTIONS

def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def start_browser(cfg: dict) -> Chrome:
    session_dir = os.path.expanduser(cfg["browser"]["session_dir"])
    subprocess.run(["pkill", "-f", f"user-data-dir={session_dir}"], capture_output=True)
    browser = Chrome(_build_options(cfg))
    tab = await browser.start()
    js = _build_js_patches(cfg)
    if js:
        await tab._execute_command(
            PageCommands.add_script_to_evaluate_on_new_document(source=js, run_immediately=True)
        )
    await _inject_consent_cookie(tab, cfg)
    await tab.close()
    return browser


async def _capture_page(browser, cfg, ts):
    try:
        url, title, html, png_path = await navigate_and_capture(browser, cfg, ts)
    finally:
        await stop_browser(browser)
    return url, title, html, png_path


def _compute_status(url):
    status = "SORRY" if "/sorry/" in url else "OK"
    return status


def write_outputs(url: str, title: str, html: str, png_path: Path, status: str, ts: str) -> None:
    html_path = HTML_DIR / f"sorry_{ts}.html"
    html_path.write_text(html, encoding="utf-8")

    md_path = REPORTS_DIR / f"sorry_{ts}.md"
    if status == "SORRY":
        note = "IP block confirmed — /sorry/ redirect hit immediately. Block persists from Batch 1 stress run."
    else:
        note = "IP appears to have recovered — normal SERP returned (no /sorry/ redirect)."
    lines = [
        f"# Google Block Capture — {ts}",
        "",
        f"**Status:** {status}",
        f"**URL:** `{url}`",
        f"**Title:** {title}",
        f"**PNG:** `png/sorry_{ts}.png`",
        f"**HTML:** `html/sorry_{ts}.html`",
        "",
        note,
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_status(status, url, title, png_path, ts):
    print(f"Status: {status}", file=sys.stderr)
    print(f"URL: {url}", file=sys.stderr)
    print(f"Title: {title}", file=sys.stderr)
    print(f"PNG: {png_path}", file=sys.stderr)
    print(f"HTML: {HTML_DIR / f'sorry_{ts}.html'}", file=sys.stderr)
    print(f"MD:  {REPORTS_DIR / f'sorry_{ts}.md'}", file=sys.stderr)


def _build_options(cfg: dict) -> ChromiumOptions:
    bc = cfg["browser"]
    sc = cfg["stealth"]
    prefs = sc["browser_preferences"]
    options = ChromiumOptions()
    options.headless = bc["headless"]
    options.add_argument(f"--user-data-dir={os.path.expanduser(bc['session_dir'])}")
    options.add_argument(f"--user-agent={bc['user_agent']}")
    options.add_argument(f"--window-size={bc['window_width']},{bc['window_height']}")
    options.add_argument(f"--binary-location={bc['binary']}")
    for feat in sc.get("disable_blink_features", []):
        options.add_argument(f"--disable-blink-features={feat}")
    if sc.get("webrtc_leak_protection"):
        options.webrtc_leak_protection = True
    if sc.get("block_popups"):
        options.block_popups = True
    if sc.get("block_notifications"):
        options.block_notifications = True
    options.browser_preferences = {
        "profile": {"exit_type": "Normal", "exited_cleanly": True},
        "safebrowsing": {"enabled": prefs.get("safebrowsing", True)},
        "autofill": {"enabled": prefs.get("autofill", True)},
        "search": {"suggest_enabled": prefs.get("search_suggest", True)},
        "enable_do_not_track": prefs.get("do_not_track", False),
        "credentials_enable_service": prefs.get("credentials", True),
        "credentials_enable_autosignin": prefs.get("credentials", True),
    }
    return options


async def navigate_and_capture(browser: Chrome, cfg: dict, ts: str):
    tab = await browser.new_tab()
    js = _build_js_patches(cfg)
    if js:
        await tab._execute_command(
            PageCommands.add_script_to_evaluate_on_new_document(source=js, run_immediately=True)
        )
    await _inject_consent_cookie(tab, cfg)

    await tab.go_to(CAPTURE_URL, timeout=cfg["run"]["page_load_timeout"])
    url = await tab.current_url
    title = _extract_scalar(await tab.execute_script("return document.title")) or ""
    html = await tab.page_source

    png_path = PNG_DIR / f"sorry_{ts}.png"
    await tab.take_screenshot(path=str(png_path))
    await tab.close()
    return url, title, html, png_path


async def stop_browser(browser: Chrome) -> None:
    try:
        await browser.stop()
    except Exception:
        pass


def _build_js_patches(cfg: dict) -> str:
    patches = cfg["stealth"].get("js_patches", {})
    parts = []
    if patches.get("screen_dimensions"):
        w = cfg["browser"]["window_width"]
        h = cfg["browser"]["window_height"]
        parts.append(f"""(function() {{
    Object.defineProperty(screen, 'width', {{ get: () => {w} }});
    Object.defineProperty(screen, 'height', {{ get: () => {h} }});
    Object.defineProperty(screen, 'availWidth', {{ get: () => {w} }});
    Object.defineProperty(screen, 'availHeight', {{ get: () => {h - 23} }});
    Object.defineProperty(screen, 'colorDepth', {{ get: () => 30 }});
    Object.defineProperty(screen, 'pixelDepth', {{ get: () => 30 }});
}})();""")
    if patches.get("device_pixel_ratio"):
        parts.append("""(function() {
    Object.defineProperty(window, 'devicePixelRatio', { get: () => 2 });
})();""")
    if patches.get("outer_dimensions"):
        parts.append("""(function() {
    Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
})();""")
    if patches.get("css_active_text"):
        parts.append("""(function() {
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
})();""")
    return "\n\n".join(parts)


async def _inject_consent_cookie(tab, cfg: dict) -> None:
    cookie = cfg["google"]["consent_cookie"]
    await tab._execute_command(NetworkCommands.set_cookie(
        name=cookie["name"],
        value=cookie["value"],
        domain=cookie["domain"],
        path=cookie["path"],
        secure=cookie["secure"],
        same_site=CookieSameSite.LAX,
    ))


def _extract_scalar(result):
    if result is None:
        return None
    if isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, dict):
        level1 = result.get("result")
        if isinstance(level1, dict):
            level2 = level1.get("result")
            if isinstance(level2, dict):
                v = level2.get("value")
                if v is not None:
                    return v
    return str(result)


if __name__ == "__main__":
    asyncio.run(capture_sorry())
