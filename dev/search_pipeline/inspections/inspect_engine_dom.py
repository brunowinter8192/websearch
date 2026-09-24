#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent.parent))

from src.search.browser import new_tab, close_browser

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

DESCRIPTION = "DOM inspection tool — diagnose engine selector drift. Run when engine returns persistent EMPTY/TIMEOUT."

ENGINE_REGISTRY = {
    "semantic_scholar": {
        "build_url":      lambda q: f"https://www.semanticscholar.org/search?q={quote_plus(q)}",
        "go_timeout":     8.0,
        "exclude_domain": "semanticscholar.org",
        "current_selectors": {
            "container": "div.cl-paper-row",
            "title":     '[data-test-id="title-link"]',
            "snippet":   '[data-test-id="paper-abstract-toggle"]',
            "error":     '[data-test-id="error-message-block"]',
        },
        "dtid_keywords": [
            "paper", "result", "card", "row", "item", "article",
            "title", "abstract", "snippet", "link", "entry",
        ],
    },
    "google":         {"_todo": True},
    "google_scholar": {"_todo": True},
    "duckduckgo":     {"_todo": True},
    "mojeek":         {"_todo": True},
    "lobsters":       {"_todo": True},
}

_JS_H2 = """var _els = document.querySelectorAll('[data-test-id]');
var _ids = {};
for (var _i = 0; _i < _els.length; _i++) {
    var _v = _els[_i].getAttribute('data-test-id');
    _ids[_v] = (_ids[_v] || 0) + 1;
}
return JSON.stringify(_ids);"""

_JS_H3 = """var _els = document.querySelectorAll('div, article, li');
var _groups = {};
for (var _i = 0; _i < _els.length; _i++) {
    var _cls = _els[_i].className;
    if (!_cls || typeof _cls !== 'string' || !_cls.trim()) continue;
    var _first = _cls.trim().split(/\\s+/)[0];
    if (_first.length < 3) continue;
    _groups[_first] = (_groups[_first] || 0) + 1;
}
var _out = {};
for (var _k in _groups) { if (_groups[_k] >= 4) _out[_k] = _groups[_k]; }
return JSON.stringify(_out);"""

_JS_H4 = """var _els = document.querySelectorAll('div, article, li');
var _kw = ['paper', 'result', 'card', 'row', 'item', 'entry', 'cl-'];
var _hits = {};
for (var _i = 0; _i < _els.length; _i++) {
    var _cls = _els[_i].className;
    if (!_cls || typeof _cls !== 'string') continue;
    var _clsl = _cls.toLowerCase();
    var _first = _cls.trim().split(/\\s+/)[0];
    for (var _j = 0; _j < _kw.length; _j++) {
        if (_clsl.indexOf(_kw[_j]) !== -1) {
            var _key = _kw[_j] + ':' + _first;
            _hits[_key] = (_hits[_key] || 0) + 1;
            break;
        }
    }
}
return JSON.stringify(_hits);"""

_JS_H5 = """var _els = document.querySelectorAll('div, article');
var _attrs = {};
for (var _i = 0; _i < _els.length; _i++) {
    var _atts = _els[_i].attributes;
    for (var _j = 0; _j < _atts.length; _j++) {
        var _n = _atts[_j].name;
        if (_n.indexOf('data-') === 0) _attrs[_n] = (_attrs[_n] || 0) + 1;
    }
}
return JSON.stringify(_attrs);"""


# ORCHESTRATOR

async def run_inspection(engine_name: str, query: str, wait_s: float) -> None:
    cfg = ENGINE_REGISTRY.get(engine_name, {})
    if cfg.get("_todo"):
        print(f"ERROR: {engine_name} not yet configured (TODO stub)", file=sys.stderr)
        sys.exit(1)
    url = cfg["build_url"](query)
    print(f"Engine: {engine_name}  URL: {url}", file=sys.stderr)
    tab = await new_tab()
    try:
        await tab.go_to(url, timeout=cfg["go_timeout"])
        print(f"Navigated. Waiting {wait_s}s for JS render...", file=sys.stderr)
        await asyncio.sleep(wait_s)
        h1      = await run_js_dict(tab, _build_h1_js(cfg["current_selectors"]))
        h2_all  = await run_js_dict(tab, _JS_H2)
        h2      = {k: v for k, v in h2_all.items() if any(kw in k.lower() for kw in cfg["dtid_keywords"])}
        h3      = await run_js_dict(tab, _JS_H3)
        h4      = await run_js_dict(tab, _JS_H4)
        h5_all  = await run_js_dict(tab, _JS_H5)
        h5      = {k: v for k, v in h5_all.items() if v >= 3}
        top_cls = max(h3, key=h3.get) if h3 else None
        h6      = await run_js_str(tab, _build_h6_js(top_cls)) if top_cls else "NOT_FOUND"
        h7      = await run_js_int(tab, _build_h7_js(cfg["exclude_domain"]))
    finally:
        await tab.close()
        await close_browser()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = SCRIPT_DIR / "md" / f"{engine_name}_{ts}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_report(engine_name, query, url, wait_s, ts, h1, h2, h2_all, h3, h4, h5, h6, h7, cfg),
        encoding="utf-8",
    )
    print(f"Report: {report_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("engine", choices=list(ENGINE_REGISTRY))
    parser.add_argument("query")
    parser.add_argument("--wait-s", type=float, default=3.0, dest="wait_s",
                        help="Fixed post-navigate wait for JS rendering (default: 3.0s)")
    args = parser.parse_args()
    asyncio.run(run_inspection(args.engine, args.query, args.wait_s))


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def run_js_dict(tab, js: str) -> dict:
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


async def run_js_int(tab, js: str) -> int:
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


async def run_js_str(tab, js: str) -> str:
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    return str(val) if val is not None else ""


def _build_h1_js(selectors: dict) -> str:
    lines = ["var _c = {};"]
    for role, sel in selectors.items():
        escaped = sel.replace("'", "\\'")
        lines.append(f"_c['{role}'] = document.querySelectorAll('{escaped}').length;")
    lines.append("return JSON.stringify(_c);")
    return "\n".join(lines)


def _build_h6_js(top_class: str) -> str:
    escaped = top_class.replace("'", "\\'")
    return (
        f"var _el = document.querySelector('.{escaped}');"
        f" return _el ? _el.outerHTML.slice(0, 2000) : 'NOT_FOUND';"
    )


def _build_h7_js(exclude_domain: str) -> str:
    return "\n".join([
        "var _allA = document.querySelectorAll('a[href^=\"http\"]');",
        "var _ext = 0;",
        "for (var _i = 0; _i < _allA.length; _i++) {",
        f"    if (_allA[_i].href.indexOf('{exclude_domain}') === -1) _ext++;",
        "}",
        "return _ext;",
    ])


def diagnose(h1: dict, h2: dict, h3: dict, h7: int, cfg: dict) -> tuple[str, str]:
    container_count = h1.get("container", 0)
    if h7 == 0:
        return "BLOCKED", "H7=0 — no external links found. Page may show consent banner, CAPTCHA, or error. Try --wait-s 5."
    if container_count > 0:
        sel = cfg["current_selectors"]["container"]
        return "OK", f"Current container `{sel}` still matches {container_count}. No drift detected."
    container_kw = ["row", "card", "result", "paper", "item", "entry"]
    top_dtid = next(
        (k for k, _ in sorted(h2.items(), key=lambda x: -x[1]) if any(w in k for w in container_kw)),
        None,
    )
    top_class = max(h3, key=h3.get) if h3 else None
    if top_dtid:
        rec = f'`[data-test-id="{top_dtid}"]` (count={h2[top_dtid]}) — from H2'
    elif top_class:
        rec = f'`div.{top_class}` (count={h3[top_class]}) — from H3'
    else:
        rec = "No clear candidate — inspect H4 manually"
    return "BROKEN", (
        f"Container `{cfg['current_selectors']['container']}` matches 0. "
        f"Recommended: {rec}"
    )


def build_report(
    engine_name: str, query: str, url: str, wait_s: float, ts: str,
    h1: dict, h2: dict, h2_all: dict, h3: dict, h4: dict, h5: dict,
    h6: str, h7: int, cfg: dict,
) -> str:
    status, diag_detail = diagnose(h1, h2, h3, h7, cfg)
    L = _render_h1(engine_name, query, url, wait_s, ts, h1, cfg)
    L += _render_h2(h2, h2_all)
    L += _render_h3(h3)
    L += _render_h4(h4)
    L += _render_h5(h5)
    L += _render_h6_h7_diagnosis(h6, h7, cfg, status, diag_detail)
    return "\n".join(L)


def _render_h1(engine_name: str, query: str, url: str, wait_s: float, ts: str, h1: dict, cfg: dict) -> list[str]:
    L = [
        f"# Engine DOM Inspection — {engine_name} — {ts}",
        "",
        f"**Query:** `{query}`  **Wait:** {wait_s}s  **URL:** `{url}`",
        "",
        "## H1 — Current Selector Status",
        "",
        "| Role | Selector | Count | Status |",
        "|------|----------|-------|--------|",
    ]
    for role, sel in cfg["current_selectors"].items():
        count = h1.get(role, 0)
        flag = "✅ PRESENT" if count > 0 else "❌ BROKEN"
        L.append(f"| {role} | `{sel}` | {count} | {flag} |")
    return L


def _render_h2(h2: dict, h2_all: dict) -> list[str]:
    L = [
        "",
        "## H2 — data-test-id Inventory (semantic keywords filtered)",
        "",
        "| data-test-id | Count |",
        "|-------------|-------|",
    ]
    for k, v in sorted(h2.items(), key=lambda x: -x[1]):
        L.append(f"| `{k}` | {v} |")
    if not h2:
        L.append("| *(none matched)* | — |")
    L.append(f"*Total distinct data-test-id values on page: {len(h2_all)}*")
    return L


def _render_h3(h3: dict) -> list[str]:
    L = [
        "",
        "## H3 — Repeating Class Clusters (≥4 occurrences, top 20)",
        "",
        "| First class | Count |",
        "|-------------|-------|",
    ]
    for k, v in sorted(h3.items(), key=lambda x: -x[1])[:20]:
        L.append(f"| `{k}` | {v} |")
    if not h3:
        L.append("| *(none)* | — |")
    return L


def _render_h4(h4: dict) -> list[str]:
    L = [
        "",
        "## H4 — Class-Substring Matches (top 15)",
        "",
        "| Keyword:First-class | Count |",
        "|---------------------|-------|",
    ]
    for k, v in sorted(h4.items(), key=lambda x: -x[1])[:15]:
        L.append(f"| `{k}` | {v} |")
    if not h4:
        L.append("| *(none)* | — |")
    return L


def _render_h5(h5: dict) -> list[str]:
    L = [
        "",
        "## H5 — data-* Attribute Inventory (count ≥ 3)",
        "",
        "| Attribute | Count |",
        "|-----------|-------|",
    ]
    for k, v in sorted(h5.items(), key=lambda x: -x[1]):
        L.append(f"| `{k}` | {v} |")
    if not h5:
        L.append("| *(none)* | — |")
    return L


def _render_h6_h7_diagnosis(h6: str, h7: int, cfg: dict, status: str, diag_detail: str) -> list[str]:
    return [
        "",
        "## H6 — HTML Snippet (top H3 cluster element)",
        "",
        "```html",
        (h6[:2000] if h6 else "NOT_FOUND"),
        "```",
        "",
        "## H7 — External Link Count",
        "",
        f"External links (excl. `{cfg['exclude_domain']}`): **{h7}**  ",
        f"Results rendered: **{'YES' if h7 > 0 else 'NO — page blocked or empty'}**",
        "",
        "---",
        "",
        "## Diagnosis",
        "",
        f"**Status:** {status}",
        "",
        diag_detail,
    ]


if __name__ == "__main__":
    main()
