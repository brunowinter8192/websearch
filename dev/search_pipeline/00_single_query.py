#!/usr/bin/env python3
"""Single-query debug runner — inline flow with DOM diagnostics."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

from pydoll.browser import Chrome
from pydoll.commands import PageCommands
from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

SCRIPT_DIR = Path(__file__).parent
_spec = importlib.util.spec_from_file_location("smoke", SCRIPT_DIR / "01_google_smoke.py")
_smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_smoke)
load_config = _smoke.load_config
start_browser = _smoke.start_browser
stop_browser = _smoke.stop_browser
_build_js_patches = _smoke._build_js_patches
_inject_consent_cookie = _smoke._inject_consent_cookie
_extract_scalar = _smoke._extract_scalar

CONFIG_PATH = SCRIPT_DIR / "config.yml"


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "python asyncio best practices"
    cfg = load_config(CONFIG_PATH)
    gc = cfg["google"]
    rc = cfg["run"]
    search_url = gc["url_template"].format(query=quote_plus(query), hl=gc["hl"], num=gc["num"])

    print(f"Query : {query!r}")
    print(f"URL   : {search_url}")

    browser = await start_browser(cfg)
    tab = None
    try:
        tab = await browser.new_tab()
        await _prepare_tab(tab, cfg)
        print("Cookie injected, navigating...", flush=True)
        await _navigate_and_report(tab, search_url, rc)
        await _print_dom_snapshot(tab)
        await _print_h3_structure(tab)
        await _print_parsed_results(tab, gc)
    finally:
        await _close_tab_and_browser(tab, browser)


async def _prepare_tab(tab, cfg: dict) -> None:
    js = _build_js_patches(cfg)
    if js:
        await tab._execute_command(
            PageCommands.add_script_to_evaluate_on_new_document(source=js, run_immediately=True)
        )
    await _inject_consent_cookie(tab, cfg)


async def _navigate_and_report(tab, search_url: str, rc: dict) -> None:
    await tab.go_to(search_url, timeout=rc["page_load_timeout"])
    await asyncio.sleep(2)

    current_url = await tab.current_url
    title_raw = await tab.execute_script("return document.title")
    title = str(_extract_scalar(title_raw) or "")

    print(f"Title : {title}")
    print(f"CurURL: {current_url}")


async def _print_dom_snapshot(tab) -> None:
    # DOM snapshot
    diag_js = """return JSON.stringify({
    consent_text: (document.body||{innerText:''}).innerText.indexOf('Before you continue') !== -1,
    rso_h3: document.querySelectorAll('#rso h3').length,
    div_g: document.querySelectorAll('div.g').length,
    body_len: (document.body||{innerText:''}).innerText.length,
    body_start: (document.body||{innerText:''}).innerText.slice(0,600)
});"""
    raw = await tab.execute_script(diag_js)
    val = _extract_scalar(raw)
    if isinstance(val, str):
        d = json.loads(val)
        print("\n--- DOM SNAPSHOT ---")
        print(f"  consent_text : {d['consent_text']}")
        print(f"  #rso h3      : {d['rso_h3']}")
        print(f"  div.g        : {d['div_g']}")
        print(f"  body_len     : {d['body_len']}")
        print(f"  body_start   :\n{d['body_start']}")
        print("--- END SNAPSHOT ---")


async def _print_h3_structure(tab) -> None:
    # Per-h3 structure debug (first 3 h3s) — no IIFE, direct statements
    struct_js = """var _sh3s = document.querySelectorAll('#rso h3');
var _sout = [];
for (var _si = 0; _si < Math.min(_sh3s.length, 3); _si++) {
    var _sh3 = _sh3s[_si];
    var _smjj = _sh3.closest('.MjjYud');
    var _srsd = _sh3.closest('#rso > div');
    var _spar = _sh3.parentElement;
    var _sblk = _smjj || _srsd || _spar;
    var _sabl = _sblk ? _sblk.querySelector('a[href^="http"]') : null;
    var _sacl = _sh3.closest('a');
    _sout.push({
        title: _sh3.textContent.trim().slice(0, 40),
        MjjYud: !!_smjj, rsoDiv: !!_srsd,
        parentTag: _spar ? _spar.tagName : null,
        aBlock: _sabl ? _sabl.href.slice(0, 70) : null,
        aClose: _sacl ? _sacl.href.slice(0, 70) : null
    });
}
return JSON.stringify(_sout);"""
    raw3 = await tab.execute_script(struct_js)
    val3 = _extract_scalar(raw3)
    print(f"\n--- H3 STRUCTURE (first 3) --- [val3 type={type(val3).__name__}, repr={repr(val3)[:80]}]")
    if isinstance(val3, str):
        for entry in json.loads(val3):
            print(f"  title   : {entry['title']}")
            print(f"  MjjYud  : {entry['MjjYud']}  rsoDiv: {entry['rsoDiv']}  parentTag: {entry['parentTag']}")
            print(f"  aBlock  : {entry['aBlock']}")
            print(f"  aClose  : {entry['aClose']}")
            print()
    print("--- END H3 STRUCTURE ---")


async def _print_parsed_results(tab, gc: dict) -> None:
    # Parse via smoke parse_js
    parse_js = gc["selectors"]["parse_js"]
    raw2 = await tab.execute_script(parse_js)
    val2 = _extract_scalar(raw2)
    results = []
    if isinstance(val2, str):
        try:
            results = json.loads(val2)
        except Exception:
            pass

    print(f"\nParsed results: {len(results)}")
    for r in results[:5]:
        print(f"  [{r.get('title','')[:60]}]")
        print(f"   {r.get('url','')[:80]}")


async def _close_tab_and_browser(tab, browser) -> None:
    if tab:
        try:
            await tab.close()
        except Exception:
            pass
    await stop_browser(browser)


if __name__ == "__main__":
    asyncio.run(main())
