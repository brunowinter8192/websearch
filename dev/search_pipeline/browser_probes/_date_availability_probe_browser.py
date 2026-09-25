# INFRASTRUCTURE
import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import PageCommands, TargetCommands

SESSION_DIR = str(Path.home() / ".websearch" / "browser-session")
REAL_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
JS_FINGERPRINT_PATCHES = """
(function() {
    Object.defineProperty(screen, 'width', { get: () => 1920 });
    Object.defineProperty(screen, 'height', { get: () => 1080 });
    Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
    Object.defineProperty(screen, 'availHeight', { get: () => 1057 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 30 });
    Object.defineProperty(screen, 'pixelDepth', { get: () => 30 });
    Object.defineProperty(window, 'devicePixelRatio', { get: () => 2 });
    Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
})();
(function() {
    var _origGCS = window.getComputedStyle;
    window.getComputedStyle = function(element, pseudoElt) {
        var style = _origGCS.apply(this, arguments);
        return new Proxy(style, {
            get: function(target, name) {
                var value = target[name];
                if (name === 'color' && value === 'rgb(255, 0, 0)') { return 'rgb(0, 102, 204)'; }
                return typeof value === 'function' ? value.bind(target) : value;
            }
        });
    };
})();
"""

BLOCK_MARKERS = [
    "captcha", "unusual traffic", "verify you are human", "are you a robot",
    "access denied", "checking your browser", "temporarily blocked",
    "too many requests", "rate limit exceeded", "automated queries",
    "schieberegler ziehen", "drag the slider", "proof of work",
    "ungewöhnlichen datenverkehr", "roboter", "bestätigen sie, dass sie ein mensch",
    "confirm you are not a robot", "unusual activity", "smartcaptcha",
    "подтвердите, что запросы", "подозрительн", "ты робот",
]

_browser = None

_JS_GENERIC_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = %s;
var hit = null;
for (var i = 0; i < markers.length; i++) {
    if (body.indexOf(markers[i]) !== -1 || title.indexOf(markers[i]) !== -1) { hit = markers[i]; break; }
}
return JSON.stringify({marker: hit, url: window.location.href, ready_state: document.readyState, title: document.title});
""" % json.dumps(BLOCK_MARKERS)


# FUNCTIONS

async def _new_tab():
    global _browser
    if _browser is None:
        _kill_stale_chrome()
        _browser = Chrome(_build_options())
        await _browser.start()
    tab = await _browser.new_tab()
    await _apply_fingerprint_patches(tab)
    return tab


async def _kill_tab(tab) -> None:
    global _browser
    target_id = getattr(tab, "_target_id", None)
    if _browser is None or target_id is None:
        return
    try:
        await asyncio.wait_for(_browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0)
    except Exception as e:
        logging.warning("kill_tab failed (target_id=%s): %s", target_id, e)
    finally:
        _browser._tabs_opened.pop(target_id, None)


async def close_browser() -> None:
    global _browser
    if _browser is not None:
        await _browser.stop()
        _browser = None


async def _wait_for(tab, selector: str, cycles: int, interval: float) -> bool:
    js = f"return document.querySelectorAll('{selector}').length"
    for _ in range(cycles):
        val = _extract_value(await tab.execute_script(js))
        if val and int(val) > 0:
            return True
        await asyncio.sleep(interval)
    return False


async def _generic_diagnose(tab) -> dict:
    val = _extract_value(await tab.execute_script(_JS_GENERIC_DIAGNOSE))
    if not val:
        return {"marker": None, "url": "", "ready_state": "", "title": ""}
    return json.loads(val)


def _kill_stale_chrome():
    subprocess.run(["pkill", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True)


def _build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.headless = not os.environ.get("WEBSEARCH_HEADED")
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.block_popups = True
    options.block_notifications = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True
    options.add_argument(f"--user-agent={REAL_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    return options


async def _apply_fingerprint_patches(tab):
    await tab._execute_command(
        PageCommands.add_script_to_evaluate_on_new_document(source=JS_FINGERPRINT_PATCHES, run_immediately=True)
    )


def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None
