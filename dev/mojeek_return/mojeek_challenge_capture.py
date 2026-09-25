# INFRASTRUCTURE
import asyncio
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from _mojeek_pydoll_probe_launch import kill_tab, launch_browser, new_tab, teardown
from _mojeek_pydoll_probe_query import verify_environment_reachable

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "md"

CONTROL_URL = "https://example.org/"
SEARCH_URL = "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1"

NAV_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.2
CAPTURE_BUDGET_S = 30.0

CAPTURE_JS = """
var _w = document.querySelector('altcha-widget');
var _body = document.body ? document.body.innerText : '';
var _note = document.querySelector('#captcha-note');
var _form = document.querySelector('#altcha-form');
var _state = null;
try { _state = (_w && typeof _w.getState === 'function') ? _w.getState() : null; } catch (e) {}
var _attrs = {};
if (_w) { Array.prototype.slice.call(_w.attributes).forEach(function (a) { _attrs[a.name] = a.value; }); }
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    html_lang: document.documentElement ? document.documentElement.lang : null,
    widget_present: !!_w,
    widget_state: _state,
    widget_attributes: _attrs,
    captcha_note_text: _note ? _note.textContent : null,
    form_action: _form ? _form.getAttribute('action') : null,
    result_link_count: document.querySelectorAll('ul.results-standard > li > a.ob').length,
    literal_verification_required: _body.indexOf('Verification required') !== -1,
    literal_checking_with_server: _body.indexOf('Checking verification with server...') !== -1,
    lowercase_body_contains_captcha: _body.toLowerCase().indexOf('captcha') !== -1,
    lowercase_title_contains_captcha: document.title.toLowerCase().indexOf('captcha') !== -1,
    body_text: _body.slice(0, 700)
});
"""

FIRE_VERIFY_JS = """
var _w = document.querySelector('altcha-widget');
if (!_w || typeof _w.verify !== 'function') return JSON.stringify({fired: false});
_w.verify();
return JSON.stringify({fired: true});
"""


# ORCHESTRATOR

def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(capture_workflow())


# FUNCTIONS

async def capture_workflow() -> None:
    profile_dir = tempfile.mkdtemp(prefix="mojeek-challenge-capture-")
    handle = await launch_browser(profile_dir)
    try:
        await verify_environment_reachable(handle, CONTROL_URL)
        snapshots = await capture_challenge_page(handle)
        write_report(build_report(snapshots), REPORT_DIR)
    finally:
        await teardown(handle)
        discard_profile(profile_dir)


async def capture_challenge_page(handle) -> list[dict]:
    tab = await new_tab(handle)
    snapshots = []
    try:
        await tab.go_to(SEARCH_URL, timeout=NAV_TIMEOUT_S)
        first = await _eval_json(tab, CAPTURE_JS)
        snapshots.append({"label": "immediately after navigation", "facts": first})
        if first and first.get("widget_present"):
            await _eval_json(tab, FIRE_VERIFY_JS)
            snapshots.append({"label": "right after verify() was dispatched", "facts": await _eval_json(tab, CAPTURE_JS)})
            snapshots += await _poll_until_results(tab)
        return snapshots
    finally:
        await kill_tab(handle, tab)


def build_report(snapshots: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Mojeek challenge page, as actually served",
        "",
        f"Run: {ts}",
        f"Target: {SEARCH_URL}",
        "Live requests against mojeek.com: 1 (one navigation, cold profile).",
        "",
        "Captured to settle which strings are real. An English literal that has never been "
        "observed matching must not become an engine's block signal.",
        "",
    ]
    for snapshot in snapshots:
        lines += [
            f"## {snapshot['label']}",
            "",
            "```json",
            json.dumps(snapshot["facts"], indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    return "\n".join(lines)


def write_report(report: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"mojeek_challenge_capture_{ts}.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")
    return report_path


def discard_profile(profile_dir: str) -> None:
    shutil.rmtree(profile_dir, ignore_errors=True)


async def _poll_until_results(tab) -> list[dict]:
    snapshots = []
    seen_states = set()
    deadline = asyncio.get_event_loop().time() + CAPTURE_BUDGET_S
    while asyncio.get_event_loop().time() < deadline:
        facts = await _eval_json(tab, CAPTURE_JS)
        if facts is None:
            break
        marker = (facts.get("widget_state"), facts.get("captcha_note_text"), facts.get("result_link_count") > 0)
        if marker not in seen_states:
            seen_states.add(marker)
            snapshots.append({"label": f"state={facts.get('widget_state')} note={facts.get('captcha_note_text')!r}", "facts": facts})
        if facts.get("result_link_count", 0) > 0:
            break
        await asyncio.sleep(POLL_INTERVAL_S)
    return snapshots


async def _eval_json(tab, script: str):
    raw = await tab.execute_script(script)
    value = _extract_value(raw)
    if not value:
        return None
    return json.loads(value)


def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


if __name__ == "__main__":
    main()
