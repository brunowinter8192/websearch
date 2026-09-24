# INFRASTRUCTURE
import json
import sys
import time

import httpx
from curl_cffi import requests as curl_requests

CALL_DELAY = 0.3
IMPERSONATE_TARGET = "chrome136"

SKIP_HEADERS = frozenset({
    ":authority", ":method", ":path", ":scheme",
    "host", "content-length", "content-encoding", "transfer-encoding",
})


# FUNCTIONS

def filter_replay_headers(raw: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


def replay_httpx(url: str, headers: dict[str, str]) -> tuple[int, bytes | None, dict, str | None]:
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        return resp.status_code, resp.content, dict(resp.headers), None
    except Exception as e:
        return -1, None, {}, str(e)


def replay_curl_cffi(url: str, headers: dict[str, str]) -> tuple[int, bytes | None, dict, str | None]:
    try:
        resp = curl_requests.get(
            url, headers=headers, impersonate=IMPERSONATE_TARGET, timeout=30
        )
        return resp.status_code, resp.content, dict(resp.headers), None
    except Exception as e:
        return -1, None, {}, str(e)


def extract_cursor(body: bytes) -> tuple[str | None, str | None]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None, None

    articles = None
    if isinstance(data, list):
        articles = data
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return None, None

    last = articles[-1]
    last_id = last.get("_id") or last.get("id") or last.get("slug")
    article_dates = last.get("articleDates") or {}
    last_date = (
        article_dates.get("displayDate") or article_dates.get("publishedAt")
        or last.get("displayDate") or last.get("publishedAt") or last.get("date")
    )
    return str(last_id) if last_id else None, str(last_date) if last_date else None


def build_cursor_url(last_id: str, last_date: str) -> str:
    return (
        f"https://www.coindesk.com/api/v1/articles/timeline"
        f"?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"
    )


def count_articles(body: bytes) -> int:
    data = json.loads(body)
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return len(v)
    return 0


def extract_json_sample(body: bytes) -> dict | None:
    try:
        data = json.loads(body)
    except Exception:
        return None

    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return {"raw_keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__}

    first, last = articles[0], articles[-1]
    return {
        "total_in_response": len(articles),
        "first_article_keys": list(first.keys()),
        "last_article_id": last.get("id") or last.get("slug"),
        "last_article_display_date": last.get("displayDate") or last.get("publishedAt") or last.get("date"),
        "first_article_title": first.get("title") or first.get("headline") or "(unknown key)",
    }


def attempt_cursor_call(next_url: str, headers: dict) -> dict:
    t0 = time.monotonic()
    status_h, next_body_h, resp_hdrs_h, err_h = replay_httpx(next_url, headers)
    elapsed_h = time.monotonic() - t0

    status_c, next_body_c, resp_hdrs_c, err_c, elapsed_c = None, None, {}, None, None
    if status_h != 200:
        t0c = time.monotonic()
        status_c, next_body_c, resp_hdrs_c, err_c = replay_curl_cffi(next_url, headers)
        elapsed_c = time.monotonic() - t0c

    return {
        "status_h": status_h, "body_h": next_body_h, "hdrs_h": resp_hdrs_h, "err_h": err_h, "elapsed_h": elapsed_h,
        "status_c": status_c, "body_c": next_body_c, "hdrs_c": resp_hdrs_c, "err_c": err_c, "elapsed_c": elapsed_c,
    }


def resolve_cursor_attempt(i: int, next_url: str, headers: dict, prev_body: bytes, attempt: dict) -> dict:
    if attempt["status_h"] == 200:
        return {"ok": True, "status": attempt["status_h"], "body": attempt["body_h"],
                "err": attempt["err_h"], "elapsed": attempt["elapsed_h"]}
    if attempt["status_c"] == 200:
        return {"ok": True, "status": attempt["status_c"], "body": attempt["body_c"],
                "err": attempt["err_c"], "elapsed": attempt["elapsed_c"]}
    failure_rows = handle_cursor_failure(i, next_url, headers, prev_body, attempt)
    return {"ok": False, "rows": failure_rows}


def record_cursor_success(i: int, next_url: str, outcome: dict, last_date: str,
                           total_articles: int, oldest_date: str | None) -> tuple:
    next_body = outcome["body"]
    n_arts = count_articles(next_body) if next_body else 0
    total_articles += n_arts

    if last_date and (oldest_date is None or last_date < oldest_date):
        oldest_date = last_date

    row = {
        "call": i + 1,
        "url": next_url,
        "status": outcome["status"],
        "articles": n_arts,
        "elapsed": round(outcome["elapsed"], 2),
        "oldest_so_far": last_date[:10] if last_date else None,
        "error": outcome["err"],
    }
    return row, total_articles, oldest_date


def handle_cursor_failure(i: int, next_url: str, headers: dict, prev_body: bytes, attempt: dict) -> list:
    diag = diagnose_403(
        next_url, headers, prev_body,
        attempt["status_h"], attempt["body_h"], attempt["hdrs_h"],
        attempt["status_c"], attempt["body_c"], attempt["hdrs_c"],
    )
    rows = [{
        "call": i + 1, "url": next_url,
        "status_httpx": attempt["status_h"], "status_curl": attempt["status_c"],
        "elapsed": round(attempt["elapsed_h"], 2), "error": attempt["err_h"] or attempt["err_c"],
    }]
    rows.append({"call": "DIAG_403", **diag})
    return rows


def build_cursor_summary(results: list, total_articles: int, oldest_date: str | None) -> dict:
    ok_rows = [r for r in results if r.get("status") == 200]
    elapsed_vals = [r["elapsed"] for r in ok_rows if "elapsed" in r]
    avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 3) if elapsed_vals else None
    return {
        "call": "SUMMARY",
        "total_calls": len(ok_rows),
        "total_articles": total_articles,
        "oldest_date": oldest_date[:10] if oldest_date else None,
        "avg_elapsed": avg_elapsed,
        "non_200": len([r for r in results
                        if isinstance(r.get("call"), int)
                        and r.get("status") not in (200,)
                        and "status_httpx" in r]),
    }


def cursor_loop(
    first_url: str,
    headers: dict[str, str],
    first_body: bytes,
    n: int,
    delay: float = CALL_DELAY,
) -> list[dict]:
    results = []
    body = first_body
    prev_body = first_body
    url = first_url
    total_articles = 0
    oldest_date = None

    for i in range(n):
        last_id, last_date = extract_cursor(body)
        if not last_id or not last_date:
            results.append({"call": i + 1, "error": f"cursor extraction failed — url={url}"})
            break

        next_url = build_cursor_url(last_id, last_date)
        print(f"  call {i + 1}: {next_url}", file=sys.stderr)

        if i > 0:
            time.sleep(delay)

        attempt = attempt_cursor_call(next_url, headers)
        outcome = resolve_cursor_attempt(i, next_url, headers, prev_body, attempt)
        if not outcome["ok"]:
            results.extend(outcome["rows"])
            break

        row, total_articles, oldest_date = record_cursor_success(
            i, next_url, outcome, last_date, total_articles, oldest_date,
        )
        results.append(row)

        next_body = outcome["body"]
        if not next_body:
            break
        prev_body = body
        body = next_body
        url = next_url

    if results:
        results.append(build_cursor_summary(results, total_articles, oldest_date))

    return results


def flag_headers(hdrs: dict) -> dict:
    keys = {k.lower() for k in hdrs}
    return {
        "retry_after": hdrs.get("retry-after") or hdrs.get("Retry-After"),
        "x_ratelimit": {k: v for k, v in hdrs.items() if k.lower().startswith("x-ratelimit")},
        "server": hdrs.get("server") or hdrs.get("Server"),
        "cf_ray": hdrs.get("cf-ray") or hdrs.get("CF-Ray"),
        "cf_cache_status": hdrs.get("cf-cache-status"),
        "x_cache": hdrs.get("x-cache") or hdrs.get("X-Cache"),
        "via": hdrs.get("via") or hdrs.get("Via"),
        "all_header_names": sorted(hdrs.keys()),
    }


def test_recoverability(url: str, req_headers: dict) -> dict:
    print("  [DIAG] sleeping 10s, retrying …", file=sys.stderr)
    time.sleep(10)
    s10, _, hdrs10, _ = replay_httpx(url, req_headers)
    print(f"  [DIAG] +10s → httpx {s10}", file=sys.stderr)

    print("  [DIAG] sleeping 30s, retrying …", file=sys.stderr)
    time.sleep(30)
    s40, _, hdrs40, _ = replay_httpx(url, req_headers)
    print(f"  [DIAG] +40s → httpx {s40}", file=sys.stderr)

    return {"retry_at_10s": s10, "retry_at_40s": s40}


def diagnose_403(
    url: str,
    req_headers: dict,
    prev_body: bytes,
    status_h: int, body_h: bytes | None, resp_hdrs_h: dict,
    status_c: int | None, body_c: bytes | None, resp_hdrs_c: dict,
) -> dict:
    print(f"  [DIAG] 403 on {url} — running recoverability test …", file=sys.stderr)

    cursor_source = inspect_cursor_source(prev_body)

    body_snippet_h = (body_h or b"")[:300].decode("utf-8", errors="replace")
    body_snippet_c = (body_c or b"")[:300].decode("utf-8", errors="replace")

    recoverability = test_recoverability(url, req_headers)

    return {
        "failing_url": url,
        "status_httpx": status_h,
        "status_curl": status_c,
        "resp_headers_httpx": flag_headers(resp_hdrs_h),
        "resp_headers_curl": flag_headers(resp_hdrs_c),
        "body_snippet_httpx": body_snippet_h,
        "body_snippet_curl": body_snippet_c,
        "cursor_source_article": cursor_source,
        "recoverability": recoverability,
    }


def inspect_cursor_source(body: bytes) -> dict:
    try:
        data = json.loads(body)
    except Exception:
        return {"error": "body not JSON"}

    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return {"error": "no articles array found"}

    last = articles[-1]
    return {
        "_id": last.get("_id"),
        "storyType": last.get("storyType"),
        "articleDates": last.get("articleDates"),
        "pathname": last.get("pathname"),
        "title": last.get("title"),
    }
