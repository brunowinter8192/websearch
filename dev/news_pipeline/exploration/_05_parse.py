# INFRASTRUCTURE
import json

TIMELINE_BASE = "https://www.coindesk.com/api/v1/articles/timeline"


# FUNCTIONS

def parse_articles(body: bytes) -> list:
    data = json.loads(body)
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
            "_id": a.get("_id") or a.get("id"),
            "storyType": a.get("storyType"),
            "pathname": a.get("pathname"),
            "title": (a.get("title") or a.get("headline") or "")[:80],
            "displayDate": (
                ad.get("displayDate") or ad.get("publishedAt")
                or a.get("displayDate") or a.get("publishedAt") or a.get("date")
            ),
        })
    return result


def extract_cursor_std(articles: list) -> tuple:
    if not articles:
        return None, None
    last = articles[-1]
    return last.get("_id"), last.get("displayDate")


def build_cursor_url(last_id: str, last_date: str) -> str:
    return f"{TIMELINE_BASE}?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"
