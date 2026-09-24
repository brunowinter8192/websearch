# Seed feeders no longer turn network and parse errors into empty results (2026-09-24)

Decision record for `src/crawler/seed_feeders_navtree.py`, `seed_feeders_robots.py`, `seed_feeders_sitemap.py`. Continues `2026-08-28_robots_sitemap_seed_feeders` and `2026-08-28_navtree_seed_feeder` in this area.

## What changed

Before, five inner handlers converted failures into values that look like a genuine empty outcome:

- `_extract_next_data_payloads`: malformed `__NEXT_DATA__` JSON returned `[]`.
- `_fetch_html`, `fetch_robots_txt`, `fetch_sitemap`: an `httpx.HTTPError` returned `None`, the same value as a 404.
- `fetch_sitemap`: a corrupt `.gz` returned `None`.
- `parse_sitemap_xml`: unparseable XML returned `("unknown", [])`.

None of these conditions had ever been observed in `process-docs` or in the logs (feeder outcomes are returned as data and are not logged, so the logs cannot show them either way). The handlers were removed. The three feeder workflows already convert any exception into `FeederResult(ok=False, error=str(exc))`, so a failure now shows up in `failed_feeders` with its message instead of as a clean-looking empty source.

Kept on purpose: HTTP status returns. A 404 or any non-200 still returns `None` (`docs.github.com` has no sitemap and only a bare `User-agent: *` robots.txt, both observed), and a well-formed XML document with an unrelated root still returns `("unknown", [])`. `scope_and_dedup`'s `ValueError` drop of one malformed URL stays: it is a documented decision with a verified CPython 3.14 behaviour.

## Consequences to know

- One failing sub-sitemap now fails the whole sitemap feeder (`ok=False`), instead of losing only that sub-sitemap. One unreachable navtree version root now fails the navtree feeder for the same reason. This was named to the orchestrator before the change and accepted.
- A host that answers `/sitemap.xml` with an HTML app shell and status 200 would now make the sitemap feeder `ok=False` with a `ParseError`. Hypothesis, not observed.

## Verification

Real runs after the change, `cli.py discover_urls ... --url-file`:

| seed | ok | failed_feeders | URLs |
|---|---|---|---|
| `https://docs.python.org/3/` | True | `{}` | 29 (robots=21, seed=1, sitemap=7) |
| `https://platform.claude.com/docs` | True | `{}` | 3631 (navtree_flat=6, robots=1, seed=1, sitemap=3623) |

Tests in `dev/tests` (`test_seed_feeders_navtree.py`, `test_seed_feeders_robots.py`, `test_seed_feeders_sitemap.py`, fakes in `_seed_feeders_fakes.py`) pin each propagation and the feeder-level `ok=False` with the error text.
