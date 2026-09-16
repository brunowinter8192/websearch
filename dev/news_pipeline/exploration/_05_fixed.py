# INFRASTRUCTURE
import sys
import time

import httpx

from _05_parse import build_cursor_url, extract_cursor_std, parse_articles


# FUNCTIONS

# Fixed cursor: scan backward to find last article NOT in invalid_types
def extract_cursor_fixed(articles: list, invalid_types: frozenset) -> tuple:
    for a in reversed(articles):
        st = a.get("storyType") or ""
        if st not in invalid_types:
            aid = a.get("_id")
            adate = a.get("displayDate")
            if aid and adate:
                return aid, adate
    return extract_cursor_std(articles)


def build_fixed_row(i: int, resp, elapsed: float, articles: list, last_id: str,
                     last_date: str, cursor_overridden: bool) -> tuple:
    anchor_art = next((a for a in reversed(articles) if a.get("_id") == last_id), articles[-1])
    anchor_type = anchor_art.get("storyType")
    skipped_type = articles[-1].get("storyType") if cursor_overridden else None

    next_articles = parse_articles(resp.content) if resp.status_code == 200 else []
    n_arts = len(next_articles)

    print(
        f"  fixed call {i + 1}: {resp.status_code} ({elapsed}s)"
        f" anchor_type={anchor_type}"
        + (f" [FIXED skipped={skipped_type}]" if cursor_overridden else "")
        + f" oldest={last_date[:10]}",
        file=sys.stderr,
    )

    row = {
        "call": i + 1,
        "status": resp.status_code,
        "elapsed": elapsed,
        "articles": n_arts,
        "anchor_id": last_id,
        "anchor_storyType": anchor_type,
        "cursor_fixed": cursor_overridden,
        "skipped_storyType": skipped_type,
        "oldest_so_far": last_date[:10],
    }
    return row, n_arts


def run_fixed_iteration(body: bytes, headers: dict, delay: float, i: int, invalid_types: frozenset) -> dict:
    articles = parse_articles(body)
    if not articles:
        return {"stop": True, "row": {"call": i + 1, "error": "no articles in body"}}

    last_id, last_date = extract_cursor_fixed(articles, invalid_types)
    std_id, _ = extract_cursor_std(articles)
    cursor_overridden = (last_id != std_id)

    if not last_id or not last_date:
        return {"stop": True, "row": {"call": i + 1, "error": "no valid cursor found after filtering"}}

    next_url = build_cursor_url(last_id, last_date)

    if i > 0:
        time.sleep(delay)

    t0 = time.monotonic()
    resp = httpx.get(next_url, headers=headers, follow_redirects=True, timeout=30)
    elapsed = round(time.monotonic() - t0, 2)

    row, n_arts = build_fixed_row(i, resp, elapsed, articles, last_id, last_date, cursor_overridden)

    if resp.status_code != 200:
        row["body_snippet"] = resp.content[:400].decode("utf-8", errors="replace")
        return {"stop": True, "row": row, "n_arts": n_arts, "last_date": last_date}

    return {"stop": False, "row": row, "body": resp.content, "n_arts": n_arts, "last_date": last_date}


# Paginate n calls using fixed cursor that skips invalid storyType anchors
def fixed_cursor_loop(
    first_url: str,
    headers: dict,
    first_body: bytes,
    n: int,
    delay: float,
    invalid_types: frozenset,
) -> list:
    results: list = []
    body = first_body
    total_articles = 0
    oldest_date: str | None = None

    for i in range(n):
        outcome = run_fixed_iteration(body, headers, delay, i, invalid_types)
        results.append(outcome["row"])
        if "n_arts" in outcome:
            total_articles += outcome["n_arts"]
            last_date = outcome.get("last_date")
            if last_date and (oldest_date is None or last_date < oldest_date):
                oldest_date = last_date
        if outcome["stop"]:
            break
        body = outcome["body"]

    ok_rows = [r for r in results if r.get("status") == 200]
    elapsed_vals = [r["elapsed"] for r in ok_rows if "elapsed" in r]
    results.append({
        "call": "SUMMARY",
        "total_calls": len(ok_rows),
        "total_articles": total_articles,
        "oldest_date": oldest_date[:10] if oldest_date else None,
        "avg_elapsed": round(sum(elapsed_vals) / len(elapsed_vals), 3) if elapsed_vals else None,
        "cursor_fixed_count": sum(1 for r in results if r.get("cursor_fixed")),
        "non_200": sum(
            1 for r in results if isinstance(r.get("call"), int) and r.get("status") != 200
        ),
    })

    return results
