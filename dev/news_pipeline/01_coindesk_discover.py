#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAX_CLICK_ROUNDS = 8
POLL_INTERVAL = 0.5
POLL_MAX = 40
PRE_48H_THRESHOLD = 3
CUTOFF_DAYS = 2
DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')
OUTPUT_DIR = Path(__file__).parent / "01_json"

_JS_EXTRACT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var links = document.querySelectorAll('a[href]');
    var results = [];
    var seen = {};
    for (var i = 0; i < links.length; i++) {
        var a = links[i];
        var href = a.href;
        if (!dateRe.test(href) || seen[href]) continue;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (skip) continue;
        seen[href] = true;
        var timeLabel = '';
        node = a;
        for (var d = 0; d < 10; d++) {
            node = node.parentElement;
            if (!node) break;
            var te = node.querySelector('time');
            if (te) { timeLabel = te.getAttribute('datetime') || te.textContent.trim(); break; }
            var kids = node.querySelectorAll('span, p, div');
            for (var j = 0; j < kids.length; j++) {
                var t = kids[j].textContent.trim();
                if (t.length < 40 && /\\d+\\s*(min|hour|hr|day|h|m)\\s*(ago|s)?|just now/i.test(t)) {
                    timeLabel = t; break;
                }
            }
            if (timeLabel) break;
        }
        results.push({url: href, timeLabel: timeLabel, title: a.textContent.trim()});
    }
    return JSON.stringify(results);
})();
"""

_JS_COUNT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var seen = {};
    var count = 0;
    document.querySelectorAll('a[href]').forEach(function(a) {
        if (!dateRe.test(a.href) || seen[a.href]) return;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (!skip) { seen[a.href] = true; count++; }
    });
    return count;
})();
"""

_JS_CLICK_BTN = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            candidates[i].scrollIntoView({block: 'center', behavior: 'smooth'});
            candidates[i].click();
            return true;
        }
    }
    return false;
})();
"""


# ORCHESTRATOR
async def discover_workflow():
    session_dir = tempfile.mkdtemp(prefix="coindesk_discover_")
    today = datetime.now(timezone.utc).date()
    cutoff = compute_cutoff(today)
    port = get_free_port()

    print(f"Launching background Chrome on port {port} …", file=sys.stderr)
    launch_background_chrome(port, session_dir)
    ws_url = wait_for_ws_url(port)
    print(f"Connected: {ws_url}", file=sys.stderr)

    chrome = Chrome()
    tab = await chrome.connect(ws_url)
    try:
        all_urls = await run_click_loop(tab, cutoff)
    finally:
        await teardown_chrome_session(tab, chrome, port, session_dir)

    entries = build_entries(all_urls)
    entries, n_filtered = filter_live_blogs(entries)
    if n_filtered:
        print(f"Filtered {n_filtered} live-blog URLs (skipped)")
    path = write_output(entries)
    print_summary(entries, path)


# FUNCTIONS
async def run_click_loop(tab, cutoff) -> dict:
    print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
    await tab.go_to(TARGET_URL, timeout=60)
    await asyncio.sleep(3.0)

    initial = await extract_articles(tab)
    all_urls: dict[str, dict] = {a["url"]: a for a in initial}
    print(f"Batch 0: {len(initial)} initial articles", file=sys.stderr)

    for click_n in range(1, MAX_CLICK_ROUNDS + 1):
        pre = count_older_than_cutoff(list(all_urls.values()), cutoff)
        if pre >= PRE_48H_THRESHOLD:
            print(f"Coverage reached: {pre} articles older than 48h (before click {click_n}).", file=sys.stderr)
            break

        should_stop = await run_one_click(tab, click_n, all_urls, cutoff)
        if should_stop:
            break
    else:
        print(
            "WARNING: MAX_CLICK_ROUNDS reached without termination — coverage may be incomplete",
            file=sys.stderr,
        )

    return all_urls


async def run_one_click(tab, click_n: int, all_urls: dict, cutoff) -> bool:
    prev_count = len(all_urls)
    clicked = await click_button(tab)
    if not clicked:
        print(f"Button gone at click {click_n} — end of feed.", file=sys.stderr)
        return True

    await asyncio.sleep(2.0)
    await wait_for_new_articles(tab, prev_count)
    fresh = await extract_articles(tab)
    added = {a["url"]: a for a in fresh if a["url"] not in all_urls}
    all_urls.update(added)
    pre = count_older_than_cutoff(list(all_urls.values()), cutoff)
    print(f"Batch {click_n}: +{len(added)} | total={len(all_urls)} | older-than-48h={pre}", file=sys.stderr)

    if pre >= PRE_48H_THRESHOLD:
        print(f"Coverage reached: {pre} articles older than 48h after {click_n} click(s).", file=sys.stderr)
        return True
    return False


async def teardown_chrome_session(tab, chrome, port: int, session_dir: str) -> None:
    await tab.close()
    try:
        await chrome.close()
    except Exception as e:
        print(f"Chrome WS close (non-fatal): {e}", file=sys.stderr)
    kill_chrome_on_port(port)
    shutil.rmtree(session_dir, ignore_errors=True)
    print(f"Chrome on port {port} killed, session dir removed.", file=sys.stderr)

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch_background_chrome(port: int, session_dir: str) -> None:
    subprocess.run(
        [
            "open", "-gna", "Google Chrome", "--args",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={session_dir}",
            f"--user-agent={REAL_UA}",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        check=True,
    )


def wait_for_ws_url(port: int, timeout: float = 30.0) -> str:
    url = f"http://localhost:{port}/json/version"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read())
                return data["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome did not start on port {port} within {timeout}s")


def kill_chrome_on_port(port: int) -> None:
    try:
        subprocess.run(
            ["pkill", "-f", f"remote-debugging-port={port}"],
            check=False,
        )
    except Exception as e:
        print(f"pkill (non-fatal): {e}", file=sys.stderr)


def compute_cutoff(today) -> object:
    return today - timedelta(days=CUTOFF_DAYS - 1)


def _extract_value(raw):
    return raw["result"]["result"]["value"]


async def extract_articles(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_EXTRACT)
    val = _extract_value(raw)
    if not val:
        return []
    return json.loads(val)


async def click_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_BTN)
    return bool(_extract_value(raw))


async def wait_for_new_articles(tab, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        raw = await tab.execute_script(_JS_COUNT)
        count = _extract_value(raw)
        if count is not None and int(count) > prev_count:
            return int(count)
    return prev_count


def parse_url_date(url: str) -> datetime | None:
    m = DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def count_older_than_cutoff(articles: list[dict], cutoff_date) -> int:
    return sum(1 for a in articles if (d := parse_url_date(a["url"])) and d.date() < cutoff_date)


def _url_to_iso(url: str) -> str:
    dt = parse_url_date(url)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _extract_section(url: str) -> str:
    try:
        path = url.split("coindesk.com", 1)[1]
        return path.strip("/").split("/")[0]
    except (IndexError, ValueError):
        return "unknown"


def build_entries(all_urls: dict) -> list[dict]:
    entries = []
    for url, article in all_urls.items():
        iso = _url_to_iso(url)
        entries.append({
            "url": url,
            "lastmod": iso,
            "publication_date": iso,
            "title": article.get("title", ""),
            "section": _extract_section(url),
        })
    entries.sort(key=lambda e: e["lastmod"], reverse=True)
    return entries


def _is_live_blog(url: str) -> bool:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.startswith("live-")


def filter_live_blogs(entries: list[dict]) -> tuple[list[dict], int]:
    kept = [e for e in entries if not _is_live_blog(e["url"])]
    return kept, len(entries) - len(kept)


def write_output(entries: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_DIR / f"discover_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_summary(entries: list[dict], output_path: Path):
    from collections import Counter
    section_counts = Counter(e["section"] for e in entries)
    print(f"Total discovered : {len(entries)} URLs")
    print(f"Output           : {output_path}")
    print("Section distribution:")
    for section, count in section_counts.most_common():
        print(f"  {section}: {count}")


def main():
    asyncio.run(discover_workflow())


if __name__ == "__main__":
    main()
