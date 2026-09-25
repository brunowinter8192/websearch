# 03_ast_equivalence report

base: 8835d8cf9c091bbbc899113a6bcb082a6022887f

files compared: 296
top-level node multiset identical: 170
top-level node multiset differs: 126

## Files that differ

### dev/access_recovery/01_google_dom_probe.py
- only in base: Expr@19, run_probe
- only in current: run_probe, _configure_logging, _compute_html_run_dir, _compute_total_navs, _run_navigations, _print_report

### dev/access_recovery/02_google_wml_probe.py
- only in base: run_probe
- only in current: run_probe, _compute_wml_run_dir, _run_query_variants, _print_report

### dev/agentic_discovery/clean_web_Playwright.py
- only in base: main
- only in current: main, _print_no_md_files, _clean_files, _compute_reduction, _print_files_processed_cleaned

### dev/agentic_discovery/clean_web_anthropic.py
- only in base: main
- only in current: main, _print_no_files_matched, _clean_files, _compute_reduction, _print_files_processed

### dev/agentic_discovery/clean_web_cookieyes.py
- only in base: main
- only in current: main, _compute_reduction

### dev/agentic_discovery/clean_web_onetrust.py
- only in base: If@180
- only in current: run_main, _compute_test_arg, If@194

### dev/agentic_discovery/clean_web_rag_docs.py
- only in base: main
- only in current: main, _collect_pattern_files, _print_no_matching_files, _accumulate_domain_stats, _compute_total_before, _compute_total_after, _compute_reduction, _print_files_processed_header, _print_domain_stats, _print_totals_footer

### dev/agentic_discovery/clean_web_searxng.py
- only in base: main
- only in current: main, _print_error_input_directory, _read_test_file_argument, _compute_reduction

### dev/agentic_discovery/clean_web_tor.py
- only in base: main
- only in current: main, _print_no_files_found, _compute_reduction

### dev/brave_return/brave_pydoll_probe.py
- only in base: If@222
- only in current: main, If@227

### dev/browser_posture/01_launch_latency_probe.py
- only in base: run_probe
- only in current: run_probe, _compute_base_url, _measure_configs, _print_report

### dev/browser_posture/02_parallel_chrome_probe.py
- only in base: run_probe
- only in current: run_probe, _run_parallel_check, _print_report

### dev/browser_posture/03_fingerprint_patch_probe.py
- only in base: run_probe
- only in current: run_probe, _compute_artifact_url, _check_variants, _print_report

### dev/browser_posture/04_headed_chromium_probe.py
- only in base: run_probe
- only in current: run_probe, _compute_plist_path, _run_plist_variants, _print_report

### dev/browser_posture/05_cdp_headed_probe.py
- only in base: run_probe
- only in current: run_probe, _start_focus_poll, _run_cdp_headed_check, _print_report

### dev/camoufox_lane/01_launch_timeout_probe.py
- only in base: run_probe
- only in current: run_probe, _print_report

### dev/engine_reduction/openalex_pdf_probe.py
- only in base: run_probe
- only in current: run_probe, _probe_works, _print_report, _print_stopped_early

### dev/explore_pipeline/01_discovery.py
- only in base: If@147
- only in current: run_main, _compute_label, If@175

### dev/explore_pipeline/02_url_filters.py
- only in base: If@145
- only in current: run_main, _compute_label, If@169

### dev/explore_pipeline/03_strategies.py
- only in base: If@168
- only in current: run_main, If@183

### dev/explore_pipeline/04_render_recall.py
- only in base: If@272
- only in current: main, _add_arguments, _compute_only, If@304

### dev/explore_pipeline/05_playwright_bfs.py
- only in base: If@350
- only in current: main, _add_arguments, If@385

### dev/explore_pipeline/06_nextdata_probe.py
- only in base: If@331
- only in current: main, _compute_result, If@351

### dev/lane_choice/03_live_focus_probe.py
- only in base: main
- only in current: main, _add_arguments, _compute_urls

### dev/logging/01_audit.py
- only in base: audit_workflow
- only in current: audit_workflow, _print_scanning, _print_found_logger_call

### dev/mojeek_return/mojeek_challenge_capture.py
- only in base: If@163
- only in current: main, If@168

### dev/mojeek_return/mojeek_pydoll_probe.py
- only in base: If@180
- only in current: main, If@185

### dev/news_pipeline/02_coindesk_scrape.py
- only in base: main
- only in current: main, _compute_input_path

### dev/news_pipeline/02b_coindesk_scrape_fresh_context.py
- only in base: main
- only in current: main, _compute_input_path

### dev/news_pipeline/03_coindesk_cleanup.py
- only in base: main
- only in current: main, _add_arguments

### dev/news_pipeline/04_dedup.py
- only in base: main
- only in current: main, _add_arguments, _compute_input_path

### dev/news_pipeline/05_publish.py
- only in base: main
- only in current: main, _add_arguments, _print_done_article_s

### dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py
- only in base: _repo_root, Assign@25, main
- only in current: Assign@12, main, _compute_since, _print_png

### dev/news_pipeline/coindesk_proxy_riding/p0_pool.py
- only in base: load_backfill_pool
- only in current: load_backfill_pool, _try_roosterkid_sources, _try_databay_sources, _try_thespeedx_sources, _try_themiralay_sources, _try_r00tee_sources, _try_iplocate_sources, _try_sunny9577_sources, _try_aliilapro_sources, _try_dpangestuw_sources, _try_zaeem20_sources, _try_zloi_sources, _try_hookzof_sources

### dev/news_pipeline/coindesk_proxy_riding/p2_browser_rider.py
- only in base: If@224
- only in current: Import@16, Assign@18, Assign@20, Assign@22, main, _import_pool_loader, _import_url_sampler, _smoke, _load_pool, _sample_smoke_urls, _build_url_queue, _print_smoke_plan, _smoke_output_dir, _run_with_timeout, _elapsed_since, _list_raw_files, _build_smoke_report, _print_smoke_report, If@333

### dev/news_pipeline/coindesk_proxy_riding/p3_url_sampler.py
- only in base: _repo_root, Assign@19, If@95
- only in current: Import@5, ImportFrom@6, Assign@8, main, _print_sampled_urls, _count_years, _print_year_distribution, _compute_out, _print_written_to, If@130

### dev/news_pipeline/coindesk_proxy_riding/run_coindesk_riding.py
- only in base: _run
- only in current: _run, _compute_elapsed, _print_main_done_in, _print_main_report

### dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py
- only in base: If@10, main
- only in current: main, _ensure_worktree_on_path, _run_stage1_checks

### dev/news_pipeline/exploration/02_coindesk_pagination_probe.py
- only in base: If@12
- only in current: main, If@30

### dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py
- only in base: If@324
- only in current: Import@33, main, _resolve_cap, If@345

### dev/news_pipeline/exploration/04_coindesk_timeline_replay_probe.py
- only in base: If@138
- only in current: Import@29, main, _add_arguments, If@156

### dev/news_pipeline/exploration/05_coindesk_cursor_probe.py
- only in base: If@217
- only in current: Import@27, main, _add_arguments, _compute_invalid, If@254

### dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py
- only in base: warmth_probe_workflow
- only in current: warmth_probe_workflow, _compute_report_path, _capture_state, _print_warmth_report

### dev/news_pipeline/exploration/06_coindesk_full_discovery.py
- only in base: full_discovery
- only in current: full_discovery, _compute_log_path, _discover_into_log, _print_log, _discover, _log_start, _log_warmup_done, _discovery_report_path, _log_done

### dev/news_pipeline/exploration/_02_depth.py
- only in base: depth_workflow
- only in current: depth_workflow, _compute_report_path, _print_report, _discover_with_playwright, _print_depth_result

### dev/news_pipeline/prod_scrape_smoke.py
- only in base: main
- only in current: main, _print_loaded_urls_from

### dev/news_pipeline/scrape_isolation_smoke.py
- only in base: main
- only in current: main, _print_loaded_urls, _compute_b1_wall, _compute_b2_wall

### dev/news_pipeline/theblock/acquire_pipe/acquire_pipe.py
- only in base: If@126
- only in current: main, _add_arguments, If@148

### dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py
- only in base: fetch_url
- only in current: fetch_url, _proxy_url, _fetch_or_fail

### dev/news_pipeline/theblock/acquire_pipe/p3_target.py
- only in base: build_sitemap_target
- only in current: build_sitemap_target, _fetch_via_proxy

### dev/news_pipeline/theblock/acquire_pipe/p4_loop.py
- only in base: run_loop
- only in current: run_loop, _process_queue

### dev/news_pipeline/theblock/acquire_pipe/p4_race.py
- only in base: run_race
- only in current: run_race, _compute_candidates, _race_candidates, _compute_gap

### dev/news_pipeline/theblock/monosans_loader.py
- only in base: load_monosans_proxies
- only in current: load_monosans_proxies, _build_entries

### dev/news_pipeline/theblock/pipe_theblock.py
- only in base: pipe_theblock_workflow
- only in current: pipe_theblock_workflow, _print_the_block_proxy, _print_total_elapsed_s

### dev/news_pipeline/theblock/probe_48h_article_fetch.py
- only in base: If@151
- only in current: main, If@162

### dev/news_pipeline/theblock/probe_curated_theblock_cf.py
- only in base: If@158
- only in current: main, If@167

### dev/news_pipeline/theblock/probe_curl_cffi_discriminator.py
- only in base: probe_curl_cffi_discriminator_workflow
- only in current: probe_curl_cffi_discriminator_workflow, _print_loading_proxy_pool, _print_pool_summary, _print_primary_header, _compute_elapsed_primary, _print_done_in_s, _compute_passing_proxies, _run_secondary_probe, _compute_report_path, _print_report, _print_secondary_passing_proxies, _compute_elapsed_secondary, _print_secondary_elapsed

### dev/news_pipeline/theblock/probe_discovery.py
- only in base: probe_discovery_workflow
- only in current: probe_discovery_workflow, _read_sub_counts, _compute_status, _print_report_written

### dev/news_pipeline/theblock/probe_liveness.py
- only in base: probe_liveness_workflow
- only in current: probe_liveness_workflow, _compute_elapsed, _warn_on_unknown_bucket

### dev/news_pipeline/theblock/probe_pool_size.py
- only in base: probe_pool_size_workflow
- only in current: probe_pool_size_workflow, _print_proxy_pool_size, _compute_elapsed

### dev/news_pipeline/theblock/probe_repo_cf_survey.py
- only in base: probe_repo_cf_survey_workflow
- only in current: probe_repo_cf_survey_workflow, _compute_report_path, _print_repos_to_survey, _print_failed_sources, _print_repo_counts, _print_check_header, _check_repos, _print_report

### dev/news_pipeline/theblock/proxy_status_log.py
- only in base: record_run
- only in current: record_run, _fold_results, _compute_alive, _print_proxy_status_log

### dev/pipe_scraper_hardening/01_stealth_concurrency_probe.py
- only in base: probe_workflow
- only in current: probe_workflow, _print_baseline_done_wall, _print_stealth_done_wall, _print_report

### dev/scrape_pipeline/03_cleanup/clean.py
- only in base: main
- only in current: main, _compute_input_dir, _compute_output_dir

### dev/scrape_pipeline/04_overview_sweep/analyze.py
- only in base: main
- only in current: main, _compute_sweep_dir, _compute_cleanraw_dir

### dev/scrape_pipeline/04_overview_sweep/sweep.py
- only in base: main
- only in current: main, _compute_output_dir

### dev/scrape_pipeline/05_paper_mode/download.py
- only in base: main
- only in current: main, _collect_urls, _pdf_url_rows

### dev/scrape_pipeline/06_cloudflare_md_adoption.py
- only in base: main
- only in current: main, _add_arguments, _compute_out

### dev/scrape_pipeline/07_pipe_scrape_eval.py
- only in base: If@49
- only in current: run_main, If@65

### dev/scrape_pipeline/browser_eval/01_baseline.py
- only in base: run_baseline_suite
- only in current: run_baseline_suite, _print_loaded_test_domains, _run_domain_baselines, _print_suite_completed

### dev/scrape_pipeline/browser_eval/02_regression.py
- only in base: compare_all_baselines
- only in current: compare_all_baselines, _compute_baselines_dir, _compute_domain_dirs, _print_top_rule, _print_header_rule, _compare_domains, _print_bottom_rule

### dev/scrape_pipeline/browser_eval/03_browser.py
- only in base: main
- only in current: main, _open_crawler, _run_browser_checks, _print_output_saved_to

### dev/scrape_pipeline/filter_eval/04_filtering.py
- only in base: main
- only in current: main, _run_filter_checks, _print_output_saved_to

### dev/scrape_pipeline/filter_eval/06_content_source.py
- only in base: If@151
- only in current: main, _print_no_crawl_report, _list_crawl_reports, _print_domain_urls_max, _print_no_crawl_reports, _compare_reports, If@206

### dev/scrape_pipeline/garbage_eval/07_result_inspect.py
- only in base: run_result_inspection
- only in current: run_result_inspection, _compute_report_path, _inspect_urls, _print_report

### dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py
- only in base: run_fix_prototype
- only in current: run_fix_prototype, _compute_report_path, _compute_all_urls, _print_scraping_unique_urls, _print_report

### dev/scrape_pipeline/p1_pipe_scraper.py
- only in base: scrape_urls
- only in current: scrape_urls, _scrape_all, _replace_exceptions

### dev/search_pipeline/01_google_smoke.py
- only in base: Expr@17, run_smoke_test
- only in current: run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report

### dev/search_pipeline/02_burst_smoke.py
- only in base: If@261
- only in current: main, If@272

### dev/search_pipeline/04_ddg_smoke.py
- only in base: Expr@17, run_smoke_test
- only in current: run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report

### dev/search_pipeline/05_search_smoke.py
- only in base: If@206
- only in current: main, If@225

### dev/search_pipeline/08_scholar_smoke.py
- only in base: Expr@17, run_smoke_test
- only in current: run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report

### dev/search_pipeline/09_openalex_smoke.py
- only in base: Expr@16, run_smoke_test
- only in current: run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report

### dev/search_pipeline/11_pipeline_smoke.py
- only in base: If@339
- only in current: main, If@370

### dev/search_pipeline/12_max_results_probe.py
- only in base: Expr@21, run_probe
- only in current: run_probe, _configure_logging, _compute_engines, _run_engines, _print_report

### dev/search_pipeline/13_free_word_probe.py
- only in base: Expr@22, run_probe
- only in current: run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_free_word_queries, _print_report, _run_variant, _query_engine, _engine_sleep_s, _append_rows

### dev/search_pipeline/24_pydoll_teardown_verify.py
- only in base: pydoll_teardown_verify_workflow
- only in current: pydoll_teardown_verify_workflow, _compute_report_path, _compute_lines, _compute_browser_state, _append_browser_started, _append_result_table, _compute_overall, _append_overall, _append_interpretation, _print_report

### dev/search_pipeline/_capture_sorry.py
- only in base: capture_sorry
- only in current: capture_sorry, _capture_page, _compute_status, _print_status

### dev/search_pipeline/bee_probes/_acquire_probe_instrument.py
- only in base: Assign@69, Assign@70
- only in current: install_instrument, _require_limiter_internals

### dev/search_pipeline/bee_probes/_branch_probe_instrument.py
- only in base: Assign@58
- only in current: install_instrument, _require_limiter_internals

### dev/search_pipeline/bee_probes/_cdp_starvation_probe_instrument.py
- only in base: Assign@20
- only in current: install_process_msg_patch

### dev/search_pipeline/bee_probes/acquire_probe.py
- only in base: ImportFrom@13, If@133
- only in current: ImportFrom@12, main, _apply_smoke_query_limit, If@151

### dev/search_pipeline/bee_probes/branch_probe.py
- only in base: ImportFrom@14, If@153
- only in current: ImportFrom@13, main, _apply_smoke_query_limit, If@171

### dev/search_pipeline/bee_probes/cdp_starvation_probe.py
- only in base: ImportFrom@13, If@125
- only in current: ImportFrom@12, main, If@135

### dev/search_pipeline/browser_probes/25_startpage_probe.py
- only in base: Expr@19, run_probe
- only in current: run_probe, _configure_logging, _run_queries, _compute_ok_count, _compute_block_count, _print_report

### dev/search_pipeline/browser_probes/26_brave_probe.py
- only in base: Expr@19, run_probe
- only in current: run_probe, _configure_logging, _run_queries, _compute_ok_count, _compute_pow_count, _compute_under_gate, _print_report

### dev/search_pipeline/browser_probes/27_brave_headed_lane_probe.py
- only in base: Expr@18, run_probe
- only in current: run_probe, _configure_logging, _run_queries, _compute_ok_count, _compute_pow_count, _compute_under_gate, _print_report

### dev/search_pipeline/browser_probes/28_bing_probe.py
- only in base: Expr@21, run_probe
- only in current: run_probe, _configure_logging, _run_queries, _compute_ok_count, _compute_block_count, _compute_under_gate, _print_report

### dev/search_pipeline/browser_probes/29_yandex_probe.py
- only in base: Expr@19, run_probe
- only in current: run_probe, _configure_logging, _run_queries, _compute_ok_count, _compute_block_count, _compute_under_gate, _print_report

### dev/search_pipeline/browser_probes/31_date_availability_probe.py
- only in base: ImportFrom@12, Expr@15, run_probe, run_engine_query
- only in current: ImportFrom@11, run_probe, _configure_logging, _run_engines, _print_report, run_engine_query

### dev/search_pipeline/browser_probes/_date_availability_probe_nav.py
- only in base: Assign@145
- only in current: nav_funcs

### dev/search_pipeline/browser_probes/altcha_trigger_probe.py
- only in base: If@394
- only in current: main, If@399

### dev/search_pipeline/domain_probes/19_books_probe.py
- only in base: Expr@20, run_probe
- only in current: run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_books_queries, _print_report, _run_query, _query_engine, _append_rows

### dev/search_pipeline/domain_probes/20_docs_probe.py
- only in base: Expr@20, run_probe
- only in current: run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_docs_queries, _run_query, _write_and_print_report, _close_browser_quietly, _query_engine, _append_rows

### dev/search_pipeline/empty_classify_se.py
- only in base: run_classify
- only in current: run_classify, _classify_queries, _print_report

### dev/search_pipeline/google_selector_probe.py
- only in base: Expr@20, run_probe
- only in current: run_probe, _configure_logging, _print_url, _probe_page, _print_report

### dev/search_pipeline/inspections/inspect_engine_dom.py
- only in base: Expr@18, main
- only in current: main, _configure_logging

### dev/search_pipeline/no_google_burst_smoke.py
- only in base: Expr@28, Expr@31, run_smoke
- only in current: run_smoke, _configure_logging, _prepare_report_dir, _compute_report_path, _compute_engines, _print_smoke_9_engines, _run_burst_queries, _print_report_written

### dev/search_pipeline/pdf_probes/14_download_classify_probe.py
- only in base: run_probe
- only in current: run_probe, _print_pool_smoke, _print_pool_urls_to, _compute_wall_secs, _print_report

### dev/search_pipeline/pdf_probes/15_citation_pdf_followup.py
- only in base: run_probe
- only in current: run_probe, _print_pool_html_has, _compute_wall_secs, _print_report

### dev/search_pipeline/ranking_eval/clean_pool.py
- only in base: If@210
- only in current: main, _compute_v2_dir, If@222

### dev/search_pipeline/ranking_eval/pool_diff_v2_v3.py
- only in base: If@231
- only in current: main, _compute_v3_dir, If@249

### dev/search_pipeline/ranking_eval/stage4_aggregate.py
- only in base: If@328
- only in current: main, _exit_without_ts_dir, If@342

### dev/search_pipeline/ranking_eval/stage4_aggregate_v3.py
- only in base: If@288
- only in current: main, _check_input_dirs, If@305

### dev/search_pipeline/ranking_eval/value_eval_aggregate.py
- only in base: If@332
- only in current: main, _compute_ts_out, _exit_without_ts_dir, If@353

### dev/search_pipeline/report_analysis/engine_distribution_analysis.py
- only in base: Assign@17, If@18, Assign@20, run_analysis, _render_header, _render_status_aggregate
- only in current: run_analysis, _print_parsed_records, _print_report, _render_header, _render_status_aggregate, _latest_smoke_report

### dev/search_pipeline/report_analysis/engine_health_audit.py
- only in base: main
- only in current: main, _print_report_written

### dev/search_pipeline/report_analysis/inspect_query_log.py
- only in base: main
- only in current: main, _print_no_log_file, _compute_all_records, _compute_engine_run_records, _compute_workflow_records, _print_log, _compute_records, _compute_tail_records

### dev/search_pipeline/report_analysis/snippet_quality_analysis.py
- only in base: Assign@19, If@20, Assign@22, run_analysis, _render_header
- only in current: run_analysis, _compute_sample_count, _compute_og_count, _compute_meta_count, _print_parsed_records_snippets, _print_report, _print_source_stats, _print_best_by_usefulness, _print_win_shares, _render_header, _latest_smoke_report

### dev/search_pipeline/report_analysis/snippet_selection_simulator.py
- only in base: Assign@17, If@18, Assign@20, run_simulation, _render_header
- only in current: run_simulation, _print_parsed_records, _compute_results, _print_report, _render_header, _latest_smoke_report

### dev/search_pipeline/selector_js_equivalence_check.py
- only in base: main, If@111
- only in current: Expr@16, main, _compute_old_js, _compute_new_js, _compute_lines, _compare_engines, _write_report, _print_verdict, If@140

### dev/search_pipeline/with_google_decoupling_smoke.py
- only in base: Expr@19, Expr@22, run_smoke
- only in current: run_smoke, _configure_logging, _prepare_report_dir, _compute_report_path, _print_smoke_with_google, _run_queries, _compute_log_lines_written, _compute_pass_count, _print_result_checks_passed

### dev/tests/test_theblock_clean_pass.py
- only in base: Assign@19, Assign@20
- only in current: Assign@13, Assign@14

### dev/tests/test_theblock_discover.py
- only in base: _make_urls, Assign@15
- only in current: Assign@8

### dev/url_discovery/01_resume_state_probe.py
- only in base: url_discovery_probe_workflow
- only in current: url_discovery_probe_workflow, _run_experiments, _print_report

### dev/url_discovery/02_fixture_site_server.py
- only in base: If@31
- only in current: main, If@40

