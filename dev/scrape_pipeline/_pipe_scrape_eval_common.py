# INFRASTRUCTURE
import statistics
from pathlib import Path

DISCOVERED_URLS = Path(__file__).parent.parent / "explore_pipeline" / "06_discovered_urls.txt"
REPORTS_DIR = Path(__file__).parent / "md"


# FUNCTIONS

# Load URL list from discovered-URLs file
def load_urls(path: Path = DISCOVERED_URLS) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip()]


# Stratified sample: sort URLs alphabetically then pick every N-th (spreads across sections)
def stratify(urls: list[str], n: int) -> list[str]:
    sorted_urls = sorted(urls)
    step = max(1, len(sorted_urls) // n)
    return sorted_urls[::step][:n]


# Compute aggregate latency + outcome metrics from a results list
def compute_metrics(results: list[dict]) -> dict:
    ok = [r for r in results if r['outcome'] == 'ok']
    lats = sorted(r['wall_ms'] for r in ok)
    byt = sorted(r['bytes'] for r in ok)

    def pct(lst, p):
        if not lst:
            return 0
        return lst[min(int(len(lst) * p / 100), len(lst) - 1)]

    return {
        'total': len(results),
        'ok': len(ok),
        'empty': sum(1 for r in results if r['outcome'] == 'empty'),
        'http_error': sum(1 for r in results if r['outcome'] == 'http_error'),
        'waf_429': sum(1 for r in results if r['outcome'] == 'waf_429'),
        'error': sum(1 for r in results if r['outcome'] == 'error'),
        'lat_p50': pct(lats, 50),
        'lat_p95': pct(lats, 95),
        'lat_max': max(lats) if lats else 0,
        'lat_std': int(statistics.stdev(lats)) if len(lats) > 1 else 0,
        'bytes_p50': pct(byt, 50),
        'bytes_p95': pct(byt, 95),
    }
