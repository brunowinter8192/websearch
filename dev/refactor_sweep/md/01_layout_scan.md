# 01_layout_scan report

files scanned: 316 (EXEMPT=1, LIB=123, SCRIPT=117, TEST=75)
files with findings: 119
findings total: 119

## Findings by code

- GUARD_LOGIC: 35
- ORCHESTRATOR_LOGIC: 84

## Exempt files

- `dev/news_pipeline/theblock/jhao104/patches/helper/validator.py`: verbatim overlay of the vendored upstream helper/validator.py: copied over the upstream clone by jhao104/setup.sh, must stay diffable against upstream, and its decorator registration at definition time (ProxyValidator.addPreValidator) pins the definition order

## Files

### dev/access_recovery/01_google_dom_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe BinOp,JoinedStr,Try

### dev/access_recovery/02_google_wml_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe BinOp,For,JoinedStr

### dev/agentic_discovery/clean_web_Playwright.py (SCRIPT)
- ORCHESTRATOR_LOGIC main For,IfExp,JoinedStr

### dev/agentic_discovery/clean_web_anthropic.py (SCRIPT)
- ORCHESTRATOR_LOGIC main For,IfExp,JoinedStr

### dev/agentic_discovery/clean_web_cookieyes.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp

### dev/agentic_discovery/clean_web_onetrust.py (SCRIPT)
- GUARD_LOGIC

### dev/agentic_discovery/clean_web_rag_docs.py (SCRIPT)
- ORCHESTRATOR_LOGIC main BinOp,For,GeneratorExp,IfExp,JoinedStr

### dev/agentic_discovery/clean_web_searxng.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr

### dev/agentic_discovery/clean_web_tor.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr

### dev/brave_return/brave_pydoll_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/browser_posture/01_launch_latency_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/browser_posture/02_parallel_chrome_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/browser_posture/03_fingerprint_patch_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/browser_posture/04_headed_chromium_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe BinOp,JoinedStr,Try

### dev/browser_posture/05_cdp_headed_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/camoufox_lane/01_launch_timeout_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr

### dev/engine_reduction/openalex_pdf_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe AsyncWith,JoinedStr

### dev/explore_pipeline/01_discovery.py (SCRIPT)
- GUARD_LOGIC

### dev/explore_pipeline/02_url_filters.py (SCRIPT)
- GUARD_LOGIC

### dev/explore_pipeline/03_strategies.py (SCRIPT)
- GUARD_LOGIC

### dev/explore_pipeline/04_render_recall.py (SCRIPT)
- GUARD_LOGIC

### dev/explore_pipeline/05_playwright_bfs.py (SCRIPT)
- GUARD_LOGIC

### dev/explore_pipeline/06_nextdata_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/lane_choice/03_live_focus_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC main BoolOp,JoinedStr

### dev/logging/01_audit.py (SCRIPT)
- ORCHESTRATOR_LOGIC audit_workflow JoinedStr

### dev/mojeek_return/mojeek_challenge_capture.py (SCRIPT)
- GUARD_LOGIC

### dev/mojeek_return/mojeek_pydoll_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/02_coindesk_scrape.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp

### dev/news_pipeline/02b_coindesk_scrape_fresh_context.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp

### dev/news_pipeline/03_coindesk_cleanup.py (SCRIPT)
- ORCHESTRATOR_LOGIC main JoinedStr

### dev/news_pipeline/04_dedup.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr

### dev/news_pipeline/05_publish.py (SCRIPT)
- ORCHESTRATOR_LOGIC main JoinedStr

### dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr

### dev/news_pipeline/coindesk_proxy_riding/p0_pool.py (LIB)
- ORCHESTRATOR_LOGIC load_backfill_pool For

### dev/news_pipeline/coindesk_proxy_riding/p2_browser_rider.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/coindesk_proxy_riding/p3_url_sampler.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/coindesk_proxy_riding/run_coindesk_riding.py (SCRIPT)
- ORCHESTRATOR_LOGIC _run BinOp,JoinedStr

### dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py (SCRIPT)
- ORCHESTRATOR_LOGIC main Try

### dev/news_pipeline/exploration/02_coindesk_pagination_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/exploration/04_coindesk_timeline_replay_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/exploration/05_coindesk_cursor_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC warmth_probe_workflow BinOp,JoinedStr,Try

### dev/news_pipeline/exploration/06_coindesk_full_discovery.py (SCRIPT)
- ORCHESTRATOR_LOGIC full_discovery BinOp,JoinedStr,With

### dev/news_pipeline/exploration/_02_depth.py (LIB)
- ORCHESTRATOR_LOGIC depth_workflow AsyncWith,BinOp,JoinedStr

### dev/news_pipeline/prod_scrape_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC main JoinedStr

### dev/news_pipeline/scrape_isolation_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC main BinOp,JoinedStr

### dev/news_pipeline/theblock/acquire_pipe/acquire_pipe.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py (LIB)
- ORCHESTRATOR_LOGIC fetch_url JoinedStr,Try

### dev/news_pipeline/theblock/acquire_pipe/p3_target.py (LIB)
- ORCHESTRATOR_LOGIC build_sitemap_target IfExp

### dev/news_pipeline/theblock/acquire_pipe/p4_loop.py (LIB)
- ORCHESTRATOR_LOGIC run_loop While

### dev/news_pipeline/theblock/acquire_pipe/p4_race.py (LIB)
- ORCHESTRATOR_LOGIC run_race ListComp,Slice,With

### dev/news_pipeline/theblock/monosans_loader.py (LIB)
- ORCHESTRATOR_LOGIC load_monosans_proxies ListComp

### dev/news_pipeline/theblock/pipe_theblock.py (SCRIPT)
- ORCHESTRATOR_LOGIC pipe_theblock_workflow JoinedStr

### dev/news_pipeline/theblock/probe_48h_article_fetch.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/theblock/probe_curated_theblock_cf.py (SCRIPT)
- GUARD_LOGIC

### dev/news_pipeline/theblock/probe_curl_cffi_discriminator.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_curl_cffi_discriminator_workflow BinOp,JoinedStr,ListComp

### dev/news_pipeline/theblock/probe_discovery.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_discovery_workflow IfExp,JoinedStr

### dev/news_pipeline/theblock/probe_liveness.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_liveness_workflow BinOp,GeneratorExp

### dev/news_pipeline/theblock/probe_pool_size.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_pool_size_workflow BinOp,JoinedStr

### dev/news_pipeline/theblock/probe_repo_cf_survey.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_repo_cf_survey_workflow BinOp,For,JoinedStr

### dev/news_pipeline/theblock/proxy_status_log.py (LIB)
- ORCHESTRATOR_LOGIC record_run For,GeneratorExp,JoinedStr

### dev/pipe_scraper_hardening/01_stealth_concurrency_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC probe_workflow JoinedStr

### dev/scrape_pipeline/03_cleanup/clean.py (SCRIPT)
- ORCHESTRATOR_LOGIC main BinOp,IfExp

### dev/scrape_pipeline/04_overview_sweep/analyze.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp

### dev/scrape_pipeline/04_overview_sweep/sweep.py (SCRIPT)
- ORCHESTRATOR_LOGIC main BinOp

### dev/scrape_pipeline/05_paper_mode/download.py (SCRIPT)
- ORCHESTRATOR_LOGIC main For

### dev/scrape_pipeline/06_cloudflare_md_adoption.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr

### dev/scrape_pipeline/07_pipe_scrape_eval.py (SCRIPT)
- GUARD_LOGIC

### dev/scrape_pipeline/browser_eval/01_baseline.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_baseline_suite BinOp,For,JoinedStr

### dev/scrape_pipeline/browser_eval/02_regression.py (SCRIPT)
- ORCHESTRATOR_LOGIC compare_all_baselines BinOp,For,JoinedStr,ListComp

### dev/scrape_pipeline/browser_eval/03_browser.py (SCRIPT)
- ORCHESTRATOR_LOGIC main AsyncWith,For,JoinedStr

### dev/scrape_pipeline/filter_eval/04_filtering.py (SCRIPT)
- ORCHESTRATOR_LOGIC main AsyncWith,JoinedStr

### dev/scrape_pipeline/filter_eval/06_content_source.py (SCRIPT)
- GUARD_LOGIC

### dev/scrape_pipeline/garbage_eval/07_result_inspect.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_result_inspection BinOp,For,JoinedStr

### dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_fix_prototype BinOp,GeneratorExp,JoinedStr

### dev/scrape_pipeline/p1_pipe_scraper.py (LIB)
- ORCHESTRATOR_LOGIC scrape_urls AsyncWith,ListComp

### dev/search_pipeline/01_google_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke_test GeneratorExp,JoinedStr,Try

### dev/search_pipeline/02_burst_smoke.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/04_ddg_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke_test GeneratorExp,JoinedStr,Try

### dev/search_pipeline/05_search_smoke.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/08_scholar_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke_test GeneratorExp,JoinedStr,Try

### dev/search_pipeline/09_openalex_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke_test For,GeneratorExp,JoinedStr

### dev/search_pipeline/11_pipeline_smoke.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/12_max_results_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/search_pipeline/13_free_word_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe DictComp,JoinedStr,ListComp,Try

### dev/search_pipeline/24_pydoll_teardown_verify.py (SCRIPT)
- ORCHESTRATOR_LOGIC pydoll_teardown_verify_workflow BinOp,BoolOp,IfExp,JoinedStr

### dev/search_pipeline/_capture_sorry.py (SCRIPT)
- ORCHESTRATOR_LOGIC capture_sorry IfExp,JoinedStr,Try

### dev/search_pipeline/bee_probes/acquire_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/bee_probes/branch_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/bee_probes/cdp_starvation_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/browser_probes/25_startpage_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe GeneratorExp,JoinedStr,Try

### dev/search_pipeline/browser_probes/26_brave_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe GeneratorExp,JoinedStr,Try

### dev/search_pipeline/browser_probes/27_brave_headed_lane_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe GeneratorExp,JoinedStr,Try

### dev/search_pipeline/browser_probes/28_bing_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe GeneratorExp,JoinedStr,Try

### dev/search_pipeline/browser_probes/29_yandex_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe GeneratorExp,JoinedStr,Try

### dev/search_pipeline/browser_probes/31_date_availability_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/search_pipeline/browser_probes/altcha_trigger_probe.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/domain_probes/19_books_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe DictComp,JoinedStr,ListComp,Try

### dev/search_pipeline/domain_probes/20_docs_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe DictComp,ListComp,Try

### dev/search_pipeline/empty_classify_se.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_classify AsyncWith,JoinedStr

### dev/search_pipeline/google_selector_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe JoinedStr,Try

### dev/search_pipeline/no_google_burst_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke BinOp,JoinedStr,Try

### dev/search_pipeline/pdf_probes/14_download_classify_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe BinOp,JoinedStr

### dev/search_pipeline/pdf_probes/15_citation_pdf_followup.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_probe BinOp,JoinedStr

### dev/search_pipeline/ranking_eval/clean_pool.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/ranking_eval/pool_diff_v2_v3.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/ranking_eval/stage4_aggregate.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/ranking_eval/stage4_aggregate_v3.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/ranking_eval/value_eval_aggregate.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/report_analysis/engine_distribution_analysis.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_analysis JoinedStr

### dev/search_pipeline/report_analysis/engine_health_audit.py (SCRIPT)
- ORCHESTRATOR_LOGIC main JoinedStr

### dev/search_pipeline/report_analysis/inspect_query_log.py (SCRIPT)
- ORCHESTRATOR_LOGIC main IfExp,JoinedStr,ListComp,Slice

### dev/search_pipeline/report_analysis/snippet_quality_analysis.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_analysis For,GeneratorExp,JoinedStr

### dev/search_pipeline/report_analysis/snippet_selection_simulator.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_simulation JoinedStr,ListComp

### dev/search_pipeline/selector_js_equivalence_check.py (SCRIPT)
- GUARD_LOGIC

### dev/search_pipeline/with_google_decoupling_smoke.py (SCRIPT)
- ORCHESTRATOR_LOGIC run_smoke BinOp,GeneratorExp,JoinedStr,Try

### dev/url_discovery/01_resume_state_probe.py (SCRIPT)
- ORCHESTRATOR_LOGIC url_discovery_probe_workflow AsyncWith,JoinedStr

### dev/url_discovery/02_fixture_site_server.py (SCRIPT)
- GUARD_LOGIC

