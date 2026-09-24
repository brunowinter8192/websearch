# INFRASTRUCTURE


# FUNCTIONS

def collect_selector_hits(items: list[dict]) -> dict[str, dict[str, int]]:
    hits: dict[str, dict[str, int]] = {}
    for item in items:
        for field, index in (item.get("sel") or {}).items():
            counts = hits.setdefault(field, {})
            key = str(index)
            counts[key] = counts.get(key, 0) + 1
    return hits
