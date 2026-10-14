# INFRASTRUCTURE
import re
from pathlib import Path

from src.crawler.deep_dive_logger import log_deep_dive
from src.crawler.deep_dive_records import host_of
from src.scraper.scrape_logger import utc_timestamp

TMP_DIR = Path("/tmp")
DOCUMENTS_DIR = Path.home() / "Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents"
CUT_HEADER = re.compile(r"^(\S+\.md):(\d+)-(\d+)$")
INDEX_DONE = re.compile(r"^Done: (\d+) files indexed \((\d+) chunks\), (\d+) skipped, (\d+) adopted")
INDEX_ERROR_PREFIX = "Error"


# ORCHESTRATOR

def deep_dive_closing_workflow(
    domain: str, seed_url: str, collection: str, info_need: str,
    index_log: str | None = None, tmp_dir: Path = TMP_DIR, documents_dir: Path = DOCUMENTS_DIR,
) -> dict:
    index_log_path = Path(index_log) if index_log else tmp_dir / f"{collection}_index.log"
    record = build_closing_record(domain, seed_url, collection, info_need, index_log_path, tmp_dir, documents_dir / collection)
    log_deep_dive(record)
    return record


# FUNCTIONS

def build_closing_record(
    domain: str, seed_url: str, collection: str, info_need: str,
    index_log_path: Path, tmp_dir: Path, collection_dir: Path,
) -> dict:
    work_dir = tmp_dir / domain
    return {
        "record_type": "closing", "ts": utc_timestamp(),
        "host": host_of(seed_url), "domain": domain, "seed_url": seed_url,
        "collection": collection, "info_need": info_need,
        "discovered": count_lines(tmp_dir / f"{domain}_urls.txt"),
        "kept": count_lines(tmp_dir / f"{domain}_urls_culled.txt"),
        "work_files": work_files_facts(work_dir),
        "failed": failed_facts(tmp_dir / f"{domain}_failed"),
        "cuts": cut_facts(tmp_dir, domain),
        "backups": backup_classes(tmp_dir, domain),
        "collection_files": collection_facts(work_dir, collection_dir),
        "index": index_facts(index_log_path),
    }


def count_lines(path: Path) -> int | None:
    if not path.is_file():
        return None
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def work_files_facts(work_dir: Path) -> dict | None:
    if not work_dir.is_dir():
        return None
    files = sorted(work_dir.glob("*.md"))
    return {"count": len(files), "bytes": sum(f.stat().st_size for f in files)}


def failed_facts(failed_dir: Path) -> dict:
    names = sorted(f.name for f in failed_dir.glob("*.md")) if failed_dir.is_dir() else []
    return {"dir_exists": failed_dir.is_dir(), "count": len(names), "names": names}


def cut_facts(tmp_dir: Path, domain: str) -> dict:
    suffix = f"_{domain}.md"
    facts = {}
    for path in sorted(tmp_dir.glob(f"cut_*{suffix}")):
        facts[path.name[len("cut_"):-len(suffix)]] = parse_cut_file(path.read_text(encoding="utf-8"))
    return facts


def parse_cut_file(text: str) -> dict:
    headers = [m for m in (CUT_HEADER.match(line) for line in text.splitlines()) if m]
    return {
        "passages": len(headers),
        "lines": sum(int(m.group(3)) - int(m.group(2)) + 1 for m in headers),
        "files": len({m.group(1) for m in headers}),
    }


def backup_classes(tmp_dir: Path, domain: str) -> list[str]:
    prefix, suffix = f"{domain}_PRE_", "_BACKUP"
    return sorted(
        path.name[len(prefix):-len(suffix)]
        for path in tmp_dir.glob(f"{prefix}*{suffix}") if path.is_dir()
    )


def collection_facts(work_dir: Path, collection_dir: Path) -> dict | None:
    if not work_dir.is_dir() or not collection_dir.is_dir():
        return None
    names = [f.name for f in sorted(work_dir.glob("*.md"))]
    copied = [n for n in names if (collection_dir / n).is_file()]
    return {
        "copied": len(copied),
        "with_index_sidecar": sum(1 for n in copied if (collection_dir / n).with_suffix(".json").is_file()),
    }


def index_facts(log_path: Path) -> dict:
    if not log_path.is_file():
        return {"log_path": str(log_path), "log_exists": False, "done": None, "errors": []}
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return {
        "log_path": str(log_path), "log_exists": True,
        "done": parse_index_done(lines),
        "errors": [line for line in lines if line.startswith(INDEX_ERROR_PREFIX)],
    }


def parse_index_done(lines: list[str]) -> dict | None:
    matches = [m for m in (INDEX_DONE.match(line) for line in lines) if m]
    if not matches:
        return None
    files, chunks, skipped, adopted = (int(g) for g in matches[-1].groups())
    return {"files": files, "chunks": chunks, "skipped": skipped, "adopted": adopted}
