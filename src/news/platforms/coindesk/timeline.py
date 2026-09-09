# INFRASTRUCTURE
import sys
import time

import httpx

from src.news.platforms.coindesk.config import TIMELINE_BASE, TARGET_URL, CLICKS_REWARM
from src.news.platforms.coindesk.browser import browser_load_feed


# FUNCTIONS

def parse_articles(body: bytes) -> list[dict]:
    try:
        import json
        data = json.loads(body)
    except Exception:
        return []
    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break
    if not articles:
        return []
    result = []
    for a in articles:
        ad = a.get("articleDates") or {}
        result.append({
            "_id":        a.get("_id") or a.get("id"),
            "storyType":  a.get("storyType"),
            "pathname":   a.get("pathname"),
            "displayDate": (
                ad.get("displayDate") or ad.get("publishedAt")
                or a.get("displayDate") or a.get("publishedAt") or a.get("date")
            ),
            "title": a.get("title") or "",
        })
    return result


def build_cursor_url(last_id: str, last_date: str) -> str:
    return f"{TIMELINE_BASE}?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"


def fetch_feedpage(headers: dict) -> int:
    feed_hdrs = {k: v for k, v in headers.items() if k.lower() in {"user-agent", "accept-language", "accept"}}
    try:
        resp = httpx.get(TARGET_URL, headers=feed_hdrs, follow_redirects=True, timeout=30)
        return resp.status_code
    except OSError as e:
        print(f"[coindesk] fetch_feedpage error: {e}", file=sys.stderr)
        return -1


async def try_rewarm(failing_url: str, headers: dict) -> tuple[dict, bytes | None, str]:
    print("[coindesk] [rewarm] Attempting httpx feedpage re-warm …", file=sys.stderr)
    fp_status = fetch_feedpage(headers)
    print(f"[coindesk] [rewarm] httpx feedpage GET → {fp_status}", file=sys.stderr)
    time.sleep(1.0)

    resp = httpx.get(failing_url, headers=headers, follow_redirects=True, timeout=30)
    if resp.status_code == 200:
        print("[coindesk] [rewarm] httpx feedpage re-warm SUCCESS", file=sys.stderr)
        return headers, resp.content, "httpx"

    print(f"[coindesk] [rewarm] httpx failed ({resp.status_code}) → browser re-warm …", file=sys.stderr)
    new_headers, _, _ = await browser_load_feed(CLICKS_REWARM)
    if not new_headers:
        print("[coindesk] [rewarm] browser re-warm produced no headers — fatal", file=sys.stderr)
        return headers, None, "fatal"

    resp2 = httpx.get(failing_url, headers=new_headers, follow_redirects=True, timeout=30)
    if resp2.status_code == 200:
        print("[coindesk] [rewarm] browser re-warm SUCCESS (httpx feedpage insufficient)", file=sys.stderr)
        return new_headers, resp2.content, "browser"

    print(f"[coindesk] [rewarm] browser re-warm also failed ({resp2.status_code}) — fatal", file=sys.stderr)
    return headers, None, "fatal"
