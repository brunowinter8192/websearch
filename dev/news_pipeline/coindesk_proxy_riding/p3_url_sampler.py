# INFRASTRUCTURE

import random
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
        cwd=Path(__file__).parent,
        check=True,
    )
    git_common_dir = (Path(__file__).parent / result.stdout.strip()).resolve()
    return git_common_dir.parent


INVENTORY_DIR = _repo_root() / "data" / "news" / "coindesk" / "inventory"

SAMPLE_YEARS = list(range(2017, 2027))

SAMPLE_YEARS = list(range(2017, 2027))

MIN_PER_YEAR = 5


# ORCHESTRATOR

def sample_urls(n_total: int = 500, seed: int = 42) -> list[str]:
    year_lines = _load_year_lines()
    counts     = _compute_counts(year_lines, n_total)
    return _draw_sample(year_lines, counts, seed)


# FUNCTIONS

def _load_year_lines() -> dict[int, list[str]]:
    year_lines: dict[int, list[str]] = {}
    for year in SAMPLE_YEARS:
        path = INVENTORY_DIR / f"coindesk_{year}.txt"
        if not path.exists():
            continue
        lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
        if lines:
            year_lines[year] = lines
    return year_lines


def _compute_counts(year_lines: dict[int, list[str]], n_total: int) -> dict[int, int]:
    years   = sorted(year_lines)
    n_years = len(years)

    floor_total = n_years * MIN_PER_YEAR
    remainder   = max(0, n_total - floor_total)
    total_lines = sum(len(year_lines[y]) for y in years)

    counts: dict[int, int] = {}
    for y in years:
        prop      = len(year_lines[y]) / total_lines if total_lines else 0
        counts[y] = MIN_PER_YEAR + int(remainder * prop)

    assigned = sum(counts.values())
    gap      = n_total - assigned
    for y in sorted(years, key=lambda y: len(year_lines[y]), reverse=True):
        if gap <= 0:
            break
        counts[y] += 1
        gap        -= 1

    for y in years:
        counts[y] = min(counts[y], len(year_lines[y]))

    return counts


def _draw_sample(
    year_lines: dict[int, list[str]],
    counts: dict[int, int],
    seed: int,
) -> list[str]:
    rng  = random.Random(seed)
    urls: list[str] = []
    for year, n in sorted(counts.items()):
        lines  = year_lines[year]
        chosen = rng.sample(lines, n)
        for line in chosen:
            parts = line.split("\t", 1)
            url   = parts[1] if len(parts) == 2 else parts[0]
            urls.append(url)
    rng.shuffle(urls)
    return urls


if __name__ == "__main__":
    import json
    from collections import Counter

    urls = sample_urls(500)
    print(f"Sampled {len(urls)} URLs")

    year_dist: Counter = Counter()
    for u in urls:
        for part in u.split("/"):
            if part.isdigit() and 2015 <= int(part) <= 2027:
                year_dist[int(part)] += 1
                break

    print("Year distribution:")
    for y in sorted(year_dist):
        print(f"  {y}: {year_dist[y]}")

    out = Path(__file__).parent / "sample_500.json"
    out.write_text(json.dumps(urls, indent=2))
    print(f"Written to {out}")
