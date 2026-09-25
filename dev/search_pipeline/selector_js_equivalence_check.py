# INFRASTRUCTURE
import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
REPORT_DIR = SCRIPT_DIR / "md"
BASE_REV = "b6fab1d"
ENGINES = ("google", "bing", "brave", "yandex")

HTML = {
    "google": """
<div class="MjjYud"><a href="/goto?url=a1"><h3>T1</h3></a><div class="VwiC3b"><span class="YrbPuc">21 Nov 2025 — </span>snip one</div></div>
<div class="MjjYud"><div><h3>T2</h3><a href="/goto?url=a2">x</a></div><div data-sncf="1">snip two</div></div>
<div class="MjjYud"><a href="/goto?url=a3"><span class="LC20lb">T3</span></a><div class="lEBKkf">snip three</div></div>
<div class="MjjYud"><div><span class="LC20lb">T4</span><a href="/goto?url=a4">y</a></div></div>
<div class="MjjYud"><div><h3>T5</h3></div><a href="/goto?url=a5">z</a></div>
<div class="MjjYud"><h3>skipped, no anchor</h3></div>""",
    "bing": """
<ul><li class="b_algo"><h2><a href="https://e.test/1">B1</a></h2><div class="b_caption"><p>cap p</p></div><span class="news_dt">March 3, 2024</span></li>
<li class="b_algo"><h2><a href="https://e.test/2">B2</a></h2><div class="b_caption">cap div</div></li>
<li class="b_algo"><h2><a href="https://e.test/3">B3</a></h2></li>
<li class="b_algo"><h2>no anchor</h2></li></ul>""",
    "brave": """
<div data-type="web"><a href="https://e.test/1"><span class="search-snippet-title">R1</span></a><div class="snippet-content"><div class="content">s1</div></div></div>
<div data-type="web"><a href="https://e.test/2">anchor text title</a><div class="generic-snippet"><div class="content">s2</div></div></div>
<div data-type="web"><a href="https://e.test/3"><span class="search-snippet-title">R3</span></a></div>
<div data-type="web"><span>no anchor</span></div>""",
    "yandex": """
<ul><li class="serp-item"><a class="OrganicTitle-Link" href="https://e.test/1">Y1</a><div class="OrganicText"><span class="OrganicTextContentSpan">y span</span></div></li>
<li class="serp-item"><a class="OrganicTitle-Link" href="https://e.test/2">Y2</a><div class="OrganicText">y plain</div></li>
<li class="serp-item"><a class="OrganicTitle-Link" href="https://e.test/3">Y3</a></li>
<li class="serp-item"><span>no anchor</span></li></ul>""",
}


# ORCHESTRATOR

async def main() -> int:
    old_js = _compute_old_js()
    new_js = _compute_new_js()
    browser = await _start_browser()
    lines = _compute_lines()
    failures = await _compare_engines(browser, old_js, new_js, lines)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _write_report(stamp, lines)
    _print_verdict(failures)
    return failures


# FUNCTIONS

def _compute_old_js():
    old_js = {name: _load_js(_old_module(name)) for name in ENGINES}
    return old_js


def _compute_new_js():
    new_js = {name: _load_js(_new_module(name)) for name in ENGINES}
    return new_js


async def _start_browser() -> Chrome:
    options = ChromiumOptions()
    options.headless = True
    browser = Chrome(options)
    await browser.start()
    return browser


def _compute_lines():
    lines = ["# Selector JS equivalence check", "", f"base rev: {BASE_REV}", ""]
    return lines


async def _compare_engines(browser, old_js, new_js, lines):
    failures = 0
    try:
        for name in ENGINES:
            old_items = await _run(browser, HTML[name], old_js[name])
            new_items = await _run(browser, HTML[name], new_js[name])
            stripped = [{k: v for k, v in item.items() if k != "sel"} for item in new_items]
            same = stripped == old_items and all("sel" in item for item in new_items)
            failures += 0 if same else 1
            lines.append(f"- {name}: items={len(old_items)} identical_minus_sel={same} sel={[i.get('sel') for i in new_items]}")
    finally:
        await browser.stop()
    return failures


def _write_report(stamp, lines):
    (REPORT_DIR / f"selector_js_equivalence_check_{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_verdict(failures):
    print("VERDICT", "PASS" if failures == 0 else "FAIL")


def _old_module(name: str):
    source = subprocess.run(
        ["git", "show", f"{BASE_REV}:src/search/engines/{name}.py"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    path = Path(tempfile.mkdtemp()) / f"{name}_old.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"{name}_old", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_js(module) -> str:
    return module._JS_PARSE


def _new_module(name: str):
    return importlib.import_module(f"src.search.engines.{name}")


async def _run(browser: Chrome, html: str, js: str) -> list:
    tab = await browser.new_tab()
    await tab.go_to("about:blank")
    await tab.execute_script(f"document.body.innerHTML = {json.dumps(html)};")
    raw = await tab.execute_script(js)
    await tab.close()
    return json.loads(raw["result"]["result"]["value"])


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
