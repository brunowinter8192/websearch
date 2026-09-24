# INFRASTRUCTURE
import asyncio
import base64 as _base64
import gzip as _gzip
import sys
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from _02_dom import (
    OUTPUT_DIR,
    REAL_UA,
    TARGET_URL,
    _JS_BTN_STATE,
    _JS_CLICK_BTN,
    _JS_DISMISS_COOKIE,
    compute_oldest,
    extract_articles,
    wait_for_new_articles,
)
from _02_report import write_report

MAX_CLICKS = 5


# ORCHESTRATOR

def _read_post_data_sync(request) -> str | None:
    raw_b64 = request._impl_obj._initializer.get("postData")
    if not raw_b64:
        return None
    raw_bytes = _base64.b64decode(raw_b64)
    if raw_bytes[:2] == b'\x1f\x8b':
        return _gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
    return raw_bytes.decode("utf-8", errors="replace")


async def probe_workflow():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    har_path = OUTPUT_DIR / "session.har"
    report_path = OUTPUT_DIR / f"report_{ts}.md"

    print(f"HAR → {har_path}", file=sys.stderr)
    print(f"Report → {report_path}", file=sys.stderr)

    network_log: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(
            record_har_path=str(har_path),
            record_har_mode="full",
            user_agent=REAL_UA,
        )
        page = await context.new_page()
        page.on("response", lambda r: record_network_entry(r, network_log))

        all_urls = await setup_and_capture_initial(page)

        for entry in network_log:
            if entry["click_n"] is None:
                entry["click_n"] = 0

        batches = []
        oldest_date = compute_oldest(all_urls)
        batches.append(build_batch_row(0, len(all_urls), 0, oldest_date, "initial"))

        oldest_date = await run_click_loop(page, all_urls, oldest_date, network_log, batches)

        final_btn_state = await get_final_button_state(page)

        await context.close()
        await browser.close()

    click_nets = partition_network_log(network_log)

    write_report(report_path, batches, oldest_date, final_btn_state, click_nets, har_path)
    print(f"\nReport: {report_path}")
    print(f"HAR:    {har_path}")


# FUNCTIONS
async def setup_and_capture_initial(page) -> set:
    print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(3.0)

    cookie_result = await page.evaluate(_JS_DISMISS_COOKIE)
    print(f"Cookie consent: {cookie_result}", file=sys.stderr)
    await asyncio.sleep(0.5)

    all_urls: set[str] = set(await extract_articles(page))
    print(f"Batch 0: {len(all_urls)} initial articles", file=sys.stderr)
    return all_urls


async def run_click_loop(page, all_urls: set, oldest_date: str, network_log: list, batches: list) -> str:
    for click_n in range(1, MAX_CLICKS + 1):
        oldest_date, should_break = await run_click_batch(
            page, click_n, all_urls, oldest_date, network_log, batches,
        )
        if should_break:
            break
    return oldest_date


def record_network_entry(response, network_log: list) -> None:
    url = response.url
    method = response.request.method
    status = response.status
    if any(url.endswith(ext) for ext in (".js", ".css", ".png", ".woff", ".woff2", ".svg", ".ico", ".gif", ".webp")):
        return
    headers = response.request.headers
    next_action = headers.get("next-action", "")
    has_rsc = "_rsc" in url
    is_candidate = method == "POST" or has_rsc or next_action or "coindesk.com" in url
    if not is_candidate:
        return
    post_data = _read_post_data_sync(response.request) if method == "POST" else None
    network_log.append({
        "url": url,
        "method": method,
        "status": status,
        "next_action": next_action,
        "has_rsc": has_rsc,
        "post_data": post_data,
        "click_n": None,
    })


async def run_click_batch(page, click_n: int, all_urls: set, oldest_date: str,
                           network_log: list, batches: list) -> tuple:
    btn_state_pre = await page.evaluate(_JS_BTN_STATE)
    if not btn_state_pre.get("found"):
        print(f"Click {click_n}: button gone — end of feed", file=sys.stderr)
        batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "GONE"))
        return oldest_date, True
    if btn_state_pre.get("disabled"):
        print(f"Click {click_n}: button disabled — end of feed", file=sys.stderr)
        batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "DISABLED"))
        return oldest_date, True

    prev_count = len(all_urls)
    pre_net_idx = len(network_log)

    clicked = await page.evaluate(_JS_CLICK_BTN)
    if not clicked:
        print(f"Click {click_n}: JS click returned false — button vanished mid-click", file=sys.stderr)
        batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "GONE"))
        return oldest_date, True
    await asyncio.sleep(0.5)

    new_dom_count = await wait_for_new_articles(page, prev_count)
    print(f"Click {click_n}: feed grew from {prev_count} → {new_dom_count}", file=sys.stderr)

    for entry in network_log[pre_net_idx:]:
        entry["click_n"] = click_n

    fresh_urls = set(await extract_articles(page))
    new_this_click = fresh_urls - all_urls
    all_urls.update(fresh_urls)
    oldest_date = compute_oldest(all_urls)

    btn_state_post = await page.evaluate(_JS_BTN_STATE)
    if not btn_state_post.get("found"):
        btn_state = "GONE"
    elif btn_state_post.get("disabled"):
        btn_state = "DISABLED"
    else:
        btn_state = "active"

    print(f"  +{len(new_this_click)} new | total={len(all_urls)} | oldest={oldest_date} | btn={btn_state}", file=sys.stderr)
    batches.append(build_batch_row(click_n, len(all_urls), len(new_this_click), oldest_date, btn_state))

    return oldest_date, False


def build_batch_row(click_n: int, cumulative: int, new_this: int, oldest: str, btn_state: str) -> dict:
    return {
        "click_n": click_n,
        "cumulative_unique": cumulative,
        "new_this_click": new_this,
        "oldest_date": oldest,
        "btn_state": btn_state,
    }


async def get_final_button_state(page) -> str:
    final_btn_info = await page.evaluate(_JS_BTN_STATE)
    if not final_btn_info.get("found"):
        final_btn_state = "GONE"
    elif final_btn_info.get("disabled"):
        final_btn_state = "DISABLED"
    else:
        final_btn_state = "active"
    return final_btn_state


def partition_network_log(network_log: list) -> dict:
    click_nets: dict[int, list[dict]] = {}
    for entry in network_log:
        cn = entry["click_n"] if entry["click_n"] is not None else 0
        click_nets.setdefault(cn, []).append(entry)
    return click_nets
