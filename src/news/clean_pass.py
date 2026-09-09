# INFRASTRUCTURE

import logging
from pathlib import Path

from src.news.engine.dedup import pub_date_str
from src.news.platform import Platform


# FUNCTIONS

def _run_clean_pass(
    platform:       Platform,
    ok_entries:     list[dict],
    raw_dir:        Path,
    collection_dir: Path,
    log:            logging.Logger,
) -> dict:
    if not ok_entries:
        return {"n_cleaned": 0, "n_bodyless": 0, "total": 0}
    collection_dir.mkdir(parents=True, exist_ok=True)
    bodyless_path = raw_dir.parent / "clean" / "bodyless_urls.txt"
    bodyless_urls: list[str] = []
    n_cleaned = 0
    total = len(ok_entries)
    for i, entry in enumerate(ok_entries, start=1):
        h = entry["hash"]
        raw_path = raw_dir / f"{h}.md"
        if not raw_path.exists():
            log.warning(f"clean_pass: raw file missing — {raw_path}")
        else:
            raw_html = raw_path.read_text(encoding="utf-8")
            clean_md = platform.cleanup(raw_html, entry)
            if not clean_md:
                log.info(f"clean_pass: body-less — {entry['url']}")
                bodyless_urls.append(entry["url"])
            else:
                pubdate = pub_date_str(entry)
                out_path = collection_dir / f"theblock__{pubdate}__{h}.md"
                out_path.write_text(clean_md, encoding="utf-8")
                n_cleaned += 1
        if i % 200 == 0:
            log.info(f"clean progress {i}/{total} — {n_cleaned} cleaned, {len(bodyless_urls)} body-less")
    n_bodyless = len(bodyless_urls)
    if bodyless_urls:
        bodyless_path.parent.mkdir(parents=True, exist_ok=True)
        existing = set(bodyless_path.read_text(encoding="utf-8").splitlines()) if bodyless_path.exists() else set()
        merged = (existing | set(bodyless_urls)) - {""}
        bodyless_path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")
    log.info(f"clean_pass: {n_cleaned} cleaned / {n_bodyless} body-less / {total} total")
    return {"n_cleaned": n_cleaned, "n_bodyless": n_bodyless, "total": total}
