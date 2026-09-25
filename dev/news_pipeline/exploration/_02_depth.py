# INFRASTRUCTURE
import asyncio
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
from _02_report import write_depth_report

DEPTH_CAP = 150

_SKIP_EXT = (".js", ".css", ".woff", ".woff2", ".otf", ".png", ".jpg", ".jpeg",
             ".gif", ".webp", ".svg", ".ico", ".map")
_SKIP_PATH = ("/_next/static/", "/_next/image", "/api/cdn-fonts")


# ORCHESTRATOR

async def depth_workflow():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT_DIR / f"depth_report_{ts}.md"
    print(f"Report → {report_path}", file=sys.stderr)

    coindesk_log: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(user_agent=REAL_UA)
        page = await context.new_page()
        page.on("response", lambda r: record_coindesk_response(r, coindesk_log))

        all_urls, oldest_date = await setup_and_capture_initial(page)

        stop_reason, milestone_rows, oldest_date = await run_depth_click_loop(page, all_urls, oldest_date)

        final_btn_state = await get_final_button_state(page)

        await context.close()
        await browser.close()

    content_fetches, any_content_fetch = compute_content_fetch_flags(coindesk_log)

    write_depth_report(report_path, len(all_urls), oldest_date, stop_reason,
                       final_btn_state, milestone_rows, coindesk_log, any_content_fetch)

    print(f"\n=== DEPTH RESULT ===", file=sys.stderr)
    print(f"Max unique URLs : {len(all_urls)}", file=sys.stderr)
    print(f"Oldest date     : {oldest_date}", file=sys.stderr)
    print(f"Stop reason     : {stop_reason}", file=sys.stderr)
    print(f"CoinDesk content fetch ever fired: {any_content_fetch}", file=sys.stderr)
    print(f"Report: {report_path}")


# FUNCTIONS

def record_coindesk_response(response, coindesk_log: list) -> None:
    url = response.url
    if "www.coindesk.com" not in url and "coindesk.com" not in url:
        return
    if any(url.endswith(ext) for ext in _SKIP_EXT):
        return
    if any(seg in url for seg in _SKIP_PATH):
        return
    coindesk_log.append({
        "url": url,
        "method": response.request.method,
        "status": response.status,
    })


async def setup_and_capture_initial(page) -> tuple:
    print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(3.0)

    cookie_result = await page.evaluate(_JS_DISMISS_COOKIE)
    print(f"Cookie consent: {cookie_result}", file=sys.stderr)
    await asyncio.sleep(0.5)

    all_urls: set[str] = set(await extract_articles(page))
    oldest_date = compute_oldest(all_urls)
    print(f"Batch 0: {len(all_urls)} initial | oldest={oldest_date}", file=sys.stderr)
    return all_urls, oldest_date


async def run_depth_click_loop(page, all_urls: set, oldest_date: str) -> tuple:
    stop_reason = f"cap ({DEPTH_CAP} clicks)"
    milestone_rows: list[str] = []
    prev_count = len(all_urls)

    for click_n in range(1, DEPTH_CAP + 1):
        outcome = await run_depth_click(page, click_n, all_urls, prev_count)
        if outcome["stop"]:
            stop_reason = outcome["stop_reason"]
            break

        oldest_date = outcome["oldest_date"]
        prev_count = len(all_urls)

        if click_n % 10 == 0 or click_n <= 5:
            row = f"  click {click_n:>3}: total={len(all_urls):>4} | +{len(outcome['new_this']):>3} | oldest={oldest_date}"
            print(row, file=sys.stderr)
            milestone_rows.append(row.strip())

    return stop_reason, milestone_rows, oldest_date


async def get_final_button_state(page) -> str:
    final_btn_info = await page.evaluate(_JS_BTN_STATE)
    return (
        "GONE" if not final_btn_info.get("found")
        else "DISABLED" if final_btn_info.get("disabled")
        else "active"
    )


def compute_content_fetch_flags(coindesk_log: list) -> tuple:
    content_fetches = [e for e in coindesk_log if e["url"] != TARGET_URL
                       and "latest-crypto-news" not in e["url"]
                       or "_rsc" in e["url"] or "next-action" in e.get("method", "").lower()]
    any_content_fetch = bool([e for e in coindesk_log
                               if "_rsc" in e["url"]
                               or e["method"] == "POST"
                               or ("coindesk.com" in e["url"]
                                   and "latest-crypto-news" not in e["url"]
                                   and "metrics." not in e["url"]
                                   and "downloads." not in e["url"]
                                   and e["url"] != TARGET_URL)])
    return content_fetches, any_content_fetch


async def run_depth_click(page, click_n: int, all_urls: set, prev_count: int) -> dict:
    btn_state_pre = await page.evaluate(_JS_BTN_STATE)
    if not btn_state_pre.get("found"):
        return {"stop": True, "stop_reason": "button GONE"}
    if btn_state_pre.get("disabled"):
        return {"stop": True, "stop_reason": "button DISABLED"}

    clicked = await page.evaluate(_JS_CLICK_BTN)
    if not clicked:
        return {"stop": True, "stop_reason": "JS click returned false (button vanished)"}
    await asyncio.sleep(0.5)

    new_dom_count = await wait_for_new_articles(page, prev_count)

    fresh_urls = set(await extract_articles(page))
    new_this = fresh_urls - all_urls
    if not new_this:
        return {"stop": True, "stop_reason": f"plateau (no new URLs after click {click_n})"}

    all_urls.update(fresh_urls)
    oldest_date = compute_oldest(all_urls)

    return {"stop": False, "oldest_date": oldest_date, "new_this": new_this}
