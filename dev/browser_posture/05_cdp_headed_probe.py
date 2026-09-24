#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

import psutil

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

sys.path.insert(0, str(Path(__file__).parent))
from _lib import start_probe_server, stop_probe_server, get_frontmost_app
from _cdp_launch import (
    resolve_chromium_1228_bundle, self_launch_chrome, wait_for_devtools_port,
    check_cdp_http_ready, find_pid_by_profile,
)
from _cdp_teardown import kill_by_profile, kill_survivors, check_orphans
from _cdp_report import write_report, diff_cmdlines

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

LOCAL_DWELL_S = 3.0
FOCUS_POLL_INTERVAL_S = 0.25
CDP_PORT_WAIT_TIMEOUT_S = 10.0


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    bundle_path = resolve_chromium_1228_bundle()

    focus_samples: list[tuple[str, str]] = []
    stage = {"name": "reference_launch"}
    stop_event = asyncio.Event()
    poll_task = asyncio.create_task(focus_poll_loop(focus_samples, stage, stop_event))

    print("Reference: patchright-driven headed launch (probe 04 Run B shape)", file=sys.stderr)
    reference = await capture_reference_cmdline()
    await asyncio.to_thread(kill_survivors)

    user_data_dir = tempfile.mkdtemp(prefix="browser-posture-cdp-probe-")
    try:
        run_result = await _run_self_launch_and_scrape(bundle_path, user_data_dir, stage)
    finally:
        stage["name"] = "teardown"
        await asyncio.to_thread(kill_by_profile, user_data_dir)
        await asyncio.to_thread(kill_survivors)
        shutil.rmtree(user_data_dir, ignore_errors=True)
        stop_event.set()
        await poll_task

    orphans = check_orphans(user_data_dir)
    cmdline_diff = diff_cmdlines(run_result["self_cmdline"], reference["cmdline"])
    report_path = write_report(
        bundle_path, reference, run_result["self_launch_result"], run_result["cdp_http_check"],
        run_result["scrape_result"], run_result["self_cmdline"], cmdline_diff, focus_samples,
        orphans, REPORT_DIR,
    )
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Orphans after run: {len(orphans)}", file=sys.stderr)


# FUNCTIONS

async def focus_poll_loop(samples: list[tuple[str, str]], stage: dict, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        app = await asyncio.to_thread(get_frontmost_app)
        samples.append((stage["name"], app))
        await asyncio.sleep(FOCUS_POLL_INTERVAL_S)


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


async def capture_reference_cmdline() -> dict:
    server, thread, port = start_probe_server()
    url = f"http://127.0.0.1:{port}/"
    info = {"pid": None, "exe": None, "cmdline": None}
    stop_event = asyncio.Event()

    async def poll_loop():
        while not stop_event.is_set():
            if info["pid"] is None:
                proc = await asyncio.to_thread(find_chrome_descendant)
                if proc is not None:
                    try:
                        info["pid"] = proc.pid
                        info["exe"] = proc.exe()
                        info["cmdline"] = proc.cmdline()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            await asyncio.sleep(0.2)

    poll_task = asyncio.create_task(poll_loop())
    browser_config = BrowserConfig(headless=False, verbose=False, enable_stealth=True)
    adapter = UndetectedAdapter()
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_config, browser_adapter=adapter)
    run_config = CrawlerRunConfig(
        wait_until="load", page_timeout=15000, delay_before_return_html=LOCAL_DWELL_S,
        cache_mode=CacheMode.BYPASS, verbose=False,
    )
    error = None
    try:
        async with AsyncWebCrawler(config=browser_config, crawler_strategy=crawler_strategy) as crawler:
            await crawler.arun(url=url, config=run_config)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    finally:
        stop_event.set()
        await poll_task
        stop_probe_server(server, thread)

    return {"pid": info["pid"], "exe": info["exe"], "cmdline": info["cmdline"], "error": error}


async def scrape_over_cdp(port: int, stage: dict) -> dict:
    server, thread, http_port = start_probe_server()
    url = f"http://127.0.0.1:{http_port}/"
    browser_config = BrowserConfig(
        cdp_url=f"http://127.0.0.1:{port}",
        browser_mode="custom",
        enable_stealth=True,
        cdp_cleanup_on_close=True,
        verbose=False,
    )
    adapter = UndetectedAdapter()
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_config, browser_adapter=adapter)
    run_config = CrawlerRunConfig(
        wait_until="load", page_timeout=15000, delay_before_return_html=1.0,
        cache_mode=CacheMode.BYPASS, verbose=False,
    )
    try:
        stage["name"] = "cdp_connect_page_navigate"
        async with AsyncWebCrawler(config=browser_config, crawler_strategy=crawler_strategy) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            success = bool(getattr(result, "success", False)) or bool(getattr(result, "html", None))
            content_len = len(getattr(result, "html", "") or "")
            return {"success": success, "error": getattr(result, "error_message", None), "content_len": content_len}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}", "content_len": 0}
    finally:
        stop_probe_server(server, thread)


async def _run_self_launch_and_scrape(bundle_path: Path, user_data_dir: str, stage: dict) -> dict:
    self_launch_result = {"launched": False, "error": None}
    cdp_http_check = {"ready": False, "detail": None}
    scrape_result = {"success": False, "error": None, "content_len": 0}
    self_cmdline = None
    self_pid = None
    try:
        stage["name"] = "self_launch"
        print("Self-launch: open -g -n -a <chromium-1228 bundle>", file=sys.stderr)
        await asyncio.to_thread(self_launch_chrome, bundle_path, user_data_dir)
        self_launch_result["launched"] = True

        stage["name"] = "cdp_port_wait"
        print("Waiting for DevToolsActivePort...", file=sys.stderr)
        port = await asyncio.to_thread(wait_for_devtools_port, user_data_dir, CDP_PORT_WAIT_TIMEOUT_S)
        cdp_http_check = await asyncio.to_thread(check_cdp_http_ready, port)

        self_pid = await asyncio.to_thread(find_pid_by_profile, user_data_dir)
        if self_pid is not None:
            try:
                self_cmdline = psutil.Process(self_pid).cmdline()
            except psutil.Error:
                self_cmdline = None

        print(f"Connecting crawl4ai over cdp_url (port {port})...", file=sys.stderr)
        scrape_result = await scrape_over_cdp(port, stage)
    except Exception as e:
        self_launch_result["error"] = f"{type(e).__name__}: {e}"
        print(f"Self-launch/connect failed: {self_launch_result['error']}", file=sys.stderr)
    return {
        "self_launch_result": self_launch_result,
        "cdp_http_check": cdp_http_check,
        "scrape_result": scrape_result,
        "self_cmdline": self_cmdline,
        "self_pid": self_pid,
    }


if __name__ == "__main__":
    asyncio.run(run_probe())
