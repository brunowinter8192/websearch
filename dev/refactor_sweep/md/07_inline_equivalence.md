# 07_inline_equivalence report

base: 8835d8cf9c091bbbc899113a6bcb082a6022887f

files compared: 296
files with extraction helpers: 124
helpers checked: 406
files with problems: 0

## Files with problems

## Hand-edited files (verified by reading, not by inlining)

- `dev/agentic_discovery/clean_web_rag_docs.py`: print helpers renamed to state what they print
- `dev/agentic_discovery/clean_web_searxng.py`: argument read moved to _read_test_file_argument
- `dev/browser_posture/05_cdp_headed_probe.py`: focus poll setup moved to _start_focus_poll
- `dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py`: _repo_root inlined into the _ROOT constant (both branches returned p.parent)
- `dev/news_pipeline/coindesk_proxy_riding/p2_browser_rider.py`: nested async smoke function split into _smoke and eight single-purpose helpers
- `dev/news_pipeline/coindesk_proxy_riding/p3_url_sampler.py`: _repo_root inlined into the INVENTORY_DIR constant
- `dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py`: conditional sys.path setup moved into _ensure_worktree_on_path, called first by main
- `dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py`: cap if-chain moved to _resolve_cap
- `dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py`: try/finally capture block moved to _capture_state; its early return becomes return None and the caller returns on None
- `dev/news_pipeline/exploration/06_coindesk_full_discovery.py`: with-block moved to _discover_into_log; the early return becomes return False and the trailing print runs only on True
- `dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py`: try/except moved to _fetch_or_fail; the proxy URL f-string moved to _proxy_url
- `dev/news_pipeline/theblock/acquire_pipe/p3_target.py`: dead parameter removed, helper renamed _fetch_via_proxy
- `dev/news_pipeline/theblock/monosans_loader.py`: list comprehension return moved to _build_entries
- `dev/news_pipeline/theblock/probe_curl_cffi_discriminator.py`: secondary probe branch moved to _run_secondary_probe; pool summary and primary header split
- `dev/news_pipeline/theblock/probe_discovery.py`: sub_stats reads moved to _read_sub_counts
- `dev/news_pipeline/theblock/probe_repo_cf_survey.py`: per-repo check loop moved to _check_repos
- `dev/scrape_pipeline/05_paper_mode/download.py`: url collection moved to _collect_urls and _pdf_url_rows
- `dev/scrape_pipeline/browser_eval/01_baseline.py`: print helper renamed
- `dev/scrape_pipeline/browser_eval/02_regression.py`: print helper renamed
- `dev/scrape_pipeline/p1_pipe_scraper.py`: async-with gather moved to _scrape_all, exception replacement moved to _replace_exceptions
- `dev/search_pipeline/13_free_word_probe.py`: query loop split into _run_variant, _query_engine, _append_rows, _engine_sleep_s
- `dev/search_pipeline/24_pydoll_teardown_verify.py`: append helpers renamed
- `dev/search_pipeline/bee_probes/_acquire_probe_instrument.py`: import-time patch moved into install_instrument, which also wraps the locks of existing limiters
- `dev/search_pipeline/bee_probes/_branch_probe_instrument.py`: import-time patch moved into install_instrument
- `dev/search_pipeline/bee_probes/_cdp_starvation_probe_instrument.py`: import-time patch moved into install_process_msg_patch
- `dev/search_pipeline/bee_probes/acquire_probe.py`: main calls install_instrument after parsing arguments
- `dev/search_pipeline/bee_probes/branch_probe.py`: main calls install_instrument after parsing arguments
- `dev/search_pipeline/bee_probes/cdp_starvation_probe.py`: main calls install_process_msg_patch after parsing arguments
- `dev/search_pipeline/browser_probes/31_date_availability_probe.py`: uses nav_funcs() instead of NAV_FUNCS
- `dev/search_pipeline/browser_probes/_date_availability_probe_nav.py`: NAV_FUNCS dict became the function nav_funcs, its user 31_date_availability_probe.py calls it
- `dev/search_pipeline/domain_probes/19_books_probe.py`: query loop split into _run_query, _query_engine, _append_rows
- `dev/search_pipeline/domain_probes/20_docs_probe.py`: query loop split into _run_query, _query_engine, _append_rows; report write and browser close moved to two finally helpers
- `dev/search_pipeline/google_selector_probe.py`: try/finally page probe moved to _probe_page; its early return becomes return None and the caller returns on None
- `dev/search_pipeline/report_analysis/engine_distribution_analysis.py`: smoke report lookup moved from INFRASTRUCTURE into _latest_smoke_report, called first by the orchestrator
- `dev/search_pipeline/report_analysis/snippet_quality_analysis.py`: smoke report lookup moved from INFRASTRUCTURE into _latest_smoke_report, called first by the orchestrator
- `dev/search_pipeline/report_analysis/snippet_selection_simulator.py`: smoke report lookup moved from INFRASTRUCTURE into _latest_smoke_report, called first by the orchestrator
- `dev/search_pipeline/selector_js_equivalence_check.py`: sys.path.insert moved from the main guard body to INFRASTRUCTURE; the guard keeps the exit line; main was extracted by the tool and its helpers compared by hand
- `dev/tests/test_theblock_clean_pass.py`: GOOD_HASH and BODYLESS_HASH computed inline with hashlib instead of the local _hash
- `dev/tests/test_theblock_discover.py`: _ALL_URLS built by an inline comprehension; the then unused helper _make_urls deleted

