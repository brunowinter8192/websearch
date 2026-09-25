# 07_inline_equivalence report

base: 7bb68ff2199531fdd4487e716526db4f600cde6d

files compared: 291
files with extraction helpers: 119
helpers checked: 336
files with problems: 0

## Files with problems

## Hand-edited files (verified by reading, not by inlining)

- `dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py`: try/finally capture block moved to _capture_state; its early return becomes return None and the caller returns on None
- `dev/news_pipeline/exploration/06_coindesk_full_discovery.py`: with-block moved to _discover_into_log; the early return becomes return False and the trailing print runs only on True
- `dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py`: try/except moved to _fetch_or_fail; the proxy URL f-string moved to _proxy_url
- `dev/news_pipeline/theblock/monosans_loader.py`: list comprehension return moved to _build_entries
- `dev/news_pipeline/theblock/probe_repo_cf_survey.py`: per-repo check loop moved to _check_repos
- `dev/scrape_pipeline/p1_pipe_scraper.py`: async-with gather moved to _scrape_all, exception replacement moved to _replace_exceptions
- `dev/search_pipeline/google_selector_probe.py`: try/finally page probe moved to _probe_page; its early return becomes return None and the caller returns on None
- `dev/search_pipeline/selector_js_equivalence_check.py`: sys.path.insert moved from the main guard body to INFRASTRUCTURE; the guard keeps the exit line; main was extracted by the tool and its helpers compared by hand

