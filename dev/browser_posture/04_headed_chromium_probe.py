#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import sys
from pathlib import Path

import psutil

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

sys.path.insert(0, str(Path(__file__).parent))
from _lib import start_probe_server, stop_probe_server, get_frontmost_app
from _chromium_bundle import resolve_and_verify_bundle, read_lsuielement, set_lsuielement, read_codesign_status
from _chromium_teardown import kill_survivors, check_orphans
from _headed_chromium_report import write_report

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

LOCAL_DWELL_S = 3.0
FOCUS_POLL_INTERVAL_S = 0.25


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Run A: headless=True, plist untouched", file=sys.stderr)
    run_a = await observe_run(headless=True, poll_focus=False, dwell_s=LOCAL_DWELL_S)
    kill_survivors()

    print("Run B: headless=False, plist untouched (focus-poll WITHOUT fix)", file=sys.stderr)
    run_b = await observe_run(headless=False, poll_focus=True, dwell_s=LOCAL_DWELL_S)
    kill_survivors()

    bundle_path = resolve_and_verify_bundle(run_b["exe"])
    plist_path = bundle_path / "Contents" / "Info.plist"
    original_bytes = plist_path.read_bytes()
    original_lsuielement = read_lsuielement(plist_path)
    codesign_before = read_codesign_status(bundle_path)

    run_c = None
    codesign_after = None
    try:
        set_lsuielement(plist_path, True, original_bytes)
        codesign_after = read_codesign_status(bundle_path)
        print("Run C: headless=False, plist LSUIElement=true (focus-poll WITH fix)", file=sys.stderr)
        run_c = await observe_run(headless=False, poll_focus=True, dwell_s=LOCAL_DWELL_S)
    finally:
        plist_path.write_bytes(original_bytes)
        kill_survivors()
        plist_end_state = read_lsuielement(plist_path)
        plist_format_restored = plist_path.read_bytes() == original_bytes

    orphans = check_orphans()
    report_path = write_report(
        run_a, run_b, run_c, bundle_path, original_lsuielement, plist_end_state,
        plist_format_restored, codesign_before, codesign_after, orphans, REPORT_DIR,
    )
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Orphan chromium-family processes after run: {len(orphans)}", file=sys.stderr)


# FUNCTIONS

def find_chrome_descendant() -> psutil.Process | None:
    try:
        children = psutil.Process().children(recursive=True)
    except psutil.Error:
        return None
    for proc in children:
        try:
            exe = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if "ms-playwright" in exe:
            return proc
    return None


async def _poll_browser_and_focus(browser_info: dict, focus_samples: list[str], poll_focus: bool, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        if browser_info["pid"] is None:
            proc = await asyncio.to_thread(find_chrome_descendant)
            if proc is not None:
                try:
                    browser_info["pid"] = proc.pid
                    browser_info["exe"] = proc.exe()
                    browser_info["cmdline"] = proc.cmdline()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        if poll_focus:
            focus_samples.append(await asyncio.to_thread(get_frontmost_app))
        await asyncio.sleep(FOCUS_POLL_INTERVAL_S)


async def _run_crawl4ai_once(headless: bool, dwell_s: float, url: str) -> tuple[bool, str | None]:
    browser_config = BrowserConfig(headless=headless, verbose=False, enable_stealth=True)
    adapter = UndetectedAdapter()
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_config, browser_adapter=adapter)
    run_config = CrawlerRunConfig(
        wait_until="load", page_timeout=15000, delay_before_return_html=dwell_s,
        cache_mode=CacheMode.BYPASS, verbose=False,
    )
    try:
        async with AsyncWebCrawler(config=browser_config, crawler_strategy=crawler_strategy) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            launch_success = bool(getattr(result, "success", False)) or bool(getattr(result, "html", None))
            return launch_success, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def observe_run(headless: bool, poll_focus: bool, dwell_s: float) -> dict:
    server, thread, port = start_probe_server()
    url = f"http://127.0.0.1:{port}/"
    browser_info = {"pid": None, "exe": None, "cmdline": None}
    focus_samples: list[str] = []
    stop_event = asyncio.Event()

    poll_task = asyncio.create_task(_poll_browser_and_focus(browser_info, focus_samples, poll_focus, stop_event))
    launch_success = False
    error_message = None
    try:
        launch_success, error_message = await _run_crawl4ai_once(headless, dwell_s, url)
    finally:
        stop_event.set()
        await poll_task
        stop_probe_server(server, thread)

    return {
        "headless": headless,
        "launch_success": launch_success,
        "error_message": error_message,
        "pid": browser_info["pid"],
        "exe": browser_info["exe"],
        "cmdline": browser_info["cmdline"],
        "focus_samples": focus_samples,
        "chrome_frontmost_count": sum(1 for s in focus_samples if "chrome" in s.lower()),
    }


if __name__ == "__main__":
    asyncio.run(run_probe())
