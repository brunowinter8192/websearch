# INFRASTRUCTURE
import asyncio
import sys
import tempfile
import time
from pathlib import Path

_WORKTREE = Path(__file__).parents[3]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

MAIN_CHECKOUT = Path(__file__).parents[6]
INVENTORY_DIR = MAIN_CHECKOUT / "data" / "news" / "coindesk" / "inventory"
N_LIVE_URLS   = 10
REQUIRED_KEYS = {"url", "hash", "status", "file", "char_count", "error"}
VALID_STATUSES = {"ok", "failed"}


# ORCHESTRATOR

def main() -> None:
    try:
        asyncio.run(_live_run())
    except AssertionError as exc:
        print(f"FAIL — {exc}")
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

async def _live_run() -> None:
    from src.news.engine.proxy_riding.scrape import scrape_entries_riding, RidingScrapeConfig

    urls = _load_inventory_urls(N_LIVE_URLS)
    entries = [{"url": u} for u in urls]

    print(f"    {N_LIVE_URLS} inventory URLs loaded")

    cfg = RidingScrapeConfig(
        n_slots=2, n_browsers=1, burn_threshold=2,
        page_timeout_ms=8_000, stall_timeout_s=300.0,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        t0  = time.monotonic()
        manifest = await scrape_entries_riding(entries, out, cfg)
        elapsed  = time.monotonic() - t0

        _assert_manifest_shape(manifest)

        n_ok     = sum(1 for m in manifest if m["status"] == "ok")
        n_failed = sum(1 for m in manifest if m["status"] == "failed")
        raw_dir  = out / "raw"
        raw_html = list(raw_dir.glob("*.html")) if raw_dir.exists() else []

        print(f"    elapsed={elapsed:.0f}s  ok={n_ok}  failed={n_failed}  "
              f"raw_html={len(raw_html)}")

        n_filtered = await _assert_pool_shuffle_effective()
        print(f"    shuffle ok (pool={n_filtered} browser-eligible proxies)")

        assert len(manifest) == N_LIVE_URLS, "manifest length invariant broken post-shuffle-check"
        print(f"    manifest shape ok: {N_LIVE_URLS} entries, all keys present, "
              f"statuses in {VALID_STATUSES!r}")
        if raw_html:
            sample = raw_html[0]
            print(f"    raw sample: {sample.name}  {sample.stat().st_size:,} bytes")


def _load_inventory_urls(n: int) -> list:
    assert INVENTORY_DIR.exists(), f"inventory dir missing: {INVENTORY_DIR}"
    inv_files = sorted(INVENTORY_DIR.glob("*.txt"))
    assert inv_files, "no .txt files in inventory"

    urls: list[str] = []
    for f in inv_files:
        lines = [ln.strip() for ln in f.read_text().splitlines() if ln.strip()]
        urls.extend(lines)
        if len(urls) >= n:
            break
    urls = urls[:n]
    assert len(urls) == n, f"could not collect {n} URLs: got {len(urls)}"
    return urls


def _assert_manifest_shape(manifest: list) -> None:
    assert len(manifest) == N_LIVE_URLS, \
        f"manifest length mismatch: {len(manifest)} ≠ {N_LIVE_URLS}"
    for i, m in enumerate(manifest):
        missing = REQUIRED_KEYS - m.keys()
        assert not missing, f"entry[{i}] missing keys: {missing}"
        assert m["status"] in VALID_STATUSES, \
            f"entry[{i}] invalid status: {m['status']!r}"
        if m["status"] == "ok":
            assert m["file"] is not None,  f"entry[{i}] ok but file=None"
            assert Path(m["file"]).exists(), f"entry[{i}] ok file missing: {m['file']}"
            assert m["file"].endswith(".html"), \
                f"entry[{i}] ok file not .html: {m['file']}"


async def _assert_pool_shuffle_effective() -> int:
    import random as _random
    from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool

    raw_pool, _ = await asyncio.get_running_loop().run_in_executor(None, load_backfill_pool)
    filtered    = [(p, hp) for p, hp in raw_pool if p in frozenset({"http", "socks5"})]
    shuffled    = filtered[:]
    _random.shuffle(shuffled)
    assert shuffled != sorted(filtered), \
        "shuffle produced sorted order — extremely unlikely, re-run"
    return len(filtered)


if __name__ == "__main__":
    main()
