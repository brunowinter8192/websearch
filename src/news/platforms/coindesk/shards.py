# INFRASTRUCTURE
from pathlib import Path


# FUNCTIONS

def _append_to_shard(entry: dict, year_files: dict, discover_dir: Path) -> None:
    date_str = entry["publication_date"][:10]
    year = date_str[:4]
    if year not in year_files:
        p = discover_dir / f"coindesk_{year}.txt"
        year_files[year] = open(p, "a", encoding="utf-8", buffering=1)
    year_files[year].write(f"{date_str}\t{entry['url']}\n")


def load_discover(discover_dir: Path) -> set[str]:
    seen: set[str] = set()
    if not discover_dir.exists():
        return seen
    for shard in discover_dir.glob("coindesk_*.txt"):
        with open(shard, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "\t" in line:
                    seen.add(line.split("\t", 1)[1])
    return seen


def load_discover_filtered(
    discover_dir: Path,
    year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    if not discover_dir.exists():
        raise FileNotFoundError(f"coindesk discover directory missing: {discover_dir}")
    if year is not None:
        shard = discover_dir / f"coindesk_{year}.txt"
        if not shard.exists():
            raise FileNotFoundError(f"coindesk discover shard missing for year {year}: {shard}")
        shards = [shard]
    else:
        shards = sorted(discover_dir.glob("coindesk_*.txt"))
    entries: list[dict] = []
    for shard in shards:
        with open(shard, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "\t" not in line:
                    continue
                date_col, url = line.split("\t", 1)
                if from_date and date_col < from_date:
                    continue
                if to_date and date_col > to_date:
                    continue
                entries.append({
                    "url": url,
                    "publication_date": f"{date_col}T00:00:00+00:00",
                })
                if limit is not None and len(entries) >= limit:
                    return entries
    return entries
