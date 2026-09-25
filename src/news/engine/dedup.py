# INFRASTRUCTURE
import hashlib
import re
from pathlib import Path

DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


# ORCHESTRATOR

def filter_new_entries(
    entries: list[dict],
    collection_dir: Path,
    source: str,
    mode: str = "pubdate",
    exclude_urls: set[str] | None = None,
    raw_ext: str = ".md",
) -> tuple[list[dict], int, int]:
    candidates, n_excluded = _drop_excluded(entries, exclude_urls)
    new_entries, n_skip_raw = _drop_existing(candidates, collection_dir, source, mode, raw_ext)
    return new_entries, n_skip_raw, n_excluded


# FUNCTIONS

def _drop_excluded(entries: list[dict], exclude_urls: set[str] | None) -> tuple[list[dict], int]:
    candidates = []
    n_excluded = 0
    for entry in entries:
        if exclude_urls is not None and entry["url"] in exclude_urls:
            n_excluded += 1
            continue
        candidates.append(entry)
    return candidates, n_excluded


def _drop_existing(
    entries: list[dict], collection_dir: Path, source: str, mode: str, raw_ext: str,
) -> tuple[list[dict], int]:
    new_entries = []
    n_skip_raw = 0
    for entry in entries:
        h = url_hash(entry["url"])
        if mode == "hash_only":
            already_have = bool(list(collection_dir.glob(f"{source}__*__{h}.md")))
        elif mode == "raw":
            already_have = (collection_dir / f"{h}{raw_ext}").exists()
        else:
            pubdate = pub_date_str(entry)
            target = collection_dir / f"{source}__{pubdate}__{h}.md"
            already_have = target.exists()
        if already_have:
            n_skip_raw += 1
        else:
            new_entries.append(entry)
    return new_entries, n_skip_raw


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def pub_date_str(entry: dict) -> str:
    pub = entry.get("publication_date", "")
    if pub and len(pub) >= 10:
        return pub[:10]
    m = DATE_RE.search(entry.get("url", ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return "unknown"
