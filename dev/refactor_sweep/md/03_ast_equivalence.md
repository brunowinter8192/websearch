# 03_ast_equivalence report

base: 7bb68ff2199531fdd4487e716526db4f600cde6d

files compared: 292
top-level node multiset identical: 135
top-level node multiset differs: 157

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
- only in base: ImportFrom@14, Expr@17, run_smoke_test, run_query
- only in current: ImportFrom@13, run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report, run_query

### dev/search_pipeline/02_burst_smoke.py
- only in base: If@261
- only in current: main, If@272

### dev/search_pipeline/04_ddg_smoke.py
- only in base: ImportFrom@14, Expr@17, run_smoke_test, run_query
- only in current: ImportFrom@13, run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report, run_query

### dev/search_pipeline/05_search_smoke.py
- only in base: ImportFrom@14, ImportFrom@15, ImportFrom@16, ImportFrom@17, Assign@24, run_smoke, _run_query, If@206
- only in current: ImportFrom@13, ImportFrom@14, ImportFrom@15, ImportFrom@16, Assign@23, main, run_smoke, _run_query, If@225

### dev/search_pipeline/08_scholar_smoke.py
- only in base: ImportFrom@14, Expr@17, run_smoke_test, run_query
- only in current: ImportFrom@13, run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report, run_query

### dev/search_pipeline/09_openalex_smoke.py
- only in base: ImportFrom@14, Expr@16, run_smoke_test, run_query
- only in current: ImportFrom@13, run_smoke_test, _configure_logging, _run_queries, _compute_ok_count, _print_report, run_query

### dev/search_pipeline/11_pipeline_smoke.py
- only in base: If@339
- only in current: main, If@370

### dev/search_pipeline/12_max_results_probe.py
- only in base: ImportFrom@15, ImportFrom@16, ImportFrom@17, ImportFrom@18, Expr@21, run_probe, probe_single
- only in current: ImportFrom@14, ImportFrom@15, ImportFrom@16, ImportFrom@17, run_probe, _configure_logging, _compute_engines, _run_engines, _print_report, probe_single

### dev/search_pipeline/13_free_word_probe.py
- only in base: ImportFrom@16, ImportFrom@17, ImportFrom@18, ImportFrom@19, Expr@22, Assign@38, run_probe
- only in current: ImportFrom@15, ImportFrom@16, ImportFrom@17, ImportFrom@18, Assign@35, run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_free_word_queries, _print_report, _run_variant, _query_engine, _engine_sleep_s, _append_rows

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
- only in base: ImportFrom@16, ImportFrom@17, Expr@20, Assign@41, run_probe
- only in current: ImportFrom@15, ImportFrom@16, Assign@38, run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_books_queries, _print_report, _run_query, _query_engine, _append_rows

### dev/search_pipeline/domain_probes/20_docs_probe.py
- only in base: ImportFrom@13, ImportFrom@14, Expr@20, Assign@24, run_probe
- only in current: ImportFrom@12, ImportFrom@13, Assign@21, run_probe, _configure_logging, _compute_engines, _compute_run_stats, _run_docs_queries, _run_query, _write_and_print_report, _close_browser_quietly, _query_engine, _append_rows

### dev/search_pipeline/empty_classify_se.py
- only in base: run_classify
- only in current: run_classify, _classify_queries, _print_report

### dev/search_pipeline/google_selector_probe.py
- only in base: ImportFrom@15, Expr@19, run_probe, read_counts, read_structure
- only in current: ImportFrom@14, ImportFrom@15, run_probe, _configure_logging, _print_url, _probe_page, _print_report, read_counts, read_structure

### dev/search_pipeline/inspections/inspect_engine_dom.py
- only in base: Expr@18, main
- only in current: main, _configure_logging

### dev/search_pipeline/no_google_burst_smoke.py
- only in base: ImportFrom@23, ImportFrom@24, ImportFrom@26, Expr@28, Expr@31, run_smoke
- only in current: ImportFrom@22, ImportFrom@23, ImportFrom@25, run_smoke, _configure_logging, _prepare_report_dir, _compute_report_path, _compute_engines, _print_smoke_9_engines, _run_burst_queries, _print_report_written

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

### dev/tests/_chromium_scrape_fakes.py
- only in base: _patch_cdp_launch_mechanics
- only in current: _patch_cdp_launch_mechanics

### dev/tests/conftest.py
- only in base: _no_real_browser_launch
- only in current: _no_real_browser_launch

### dev/tests/test_brave_engine.py
- only in base: ImportFrom@15, test_marker_word_from_own_query_no_longer_discards_real_results, test_marker_word_in_unrelated_organic_snippet_no_longer_discards_real_results, test_genuine_pow_link_block_still_yields_no_results, test_unrelated_button_before_containers_never_leaks_into_success_diagnosis, test_light_dom_challenge_button_is_solved_and_returns_real_results, test_shadow_dom_challenge_button_is_solved_and_returns_real_results, test_stuck_challenge_gives_up_within_budget_and_records_it_was_attempted, test_pow_link_with_clickable_button_solves_challenge_instead_of_giving_up, test_real_no_challenge_fixture_never_attempts_a_click, test_stuck_challenge_cancelled_mid_loop_leaves_partial_facts_behind
- only in current: test_marker_word_from_own_query_no_longer_discards_real_results, test_marker_word_in_unrelated_organic_snippet_no_longer_discards_real_results, test_genuine_pow_link_block_still_yields_no_results, test_unrelated_button_before_containers_never_leaks_into_success_diagnosis, test_light_dom_challenge_button_is_solved_and_returns_real_results, test_shadow_dom_challenge_button_is_solved_and_returns_real_results, test_stuck_challenge_gives_up_within_budget_and_records_it_was_attempted, test_pow_link_with_clickable_button_solves_challenge_instead_of_giving_up, test_real_no_challenge_fixture_never_attempts_a_click, test_stuck_challenge_cancelled_mid_loop_leaves_partial_facts_behind

### dev/tests/test_browser.py
- only in base: test_reap_session_profile_kills_parsed_pids_and_cleans_leftover_directories, test_reap_session_profile_no_survivors_still_cleans_leftover_directories, test_terminate_then_kill_terminates_and_waits, test_terminate_then_kill_force_kills_survivors, test_terminate_then_kill_skips_already_dead_pid, test_kill_own_chrome_full_teardown_sequence, test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises
- only in current: test_reap_session_profile_kills_parsed_pids_and_cleans_leftover_directories, test_reap_session_profile_no_survivors_still_cleans_leftover_directories, test_kill_own_chrome_full_teardown_sequence, test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises

### dev/tests/test_browser_get_tab.py
- only in base: _patch_launch_mechanics, test_get_tab_orders_lock_reap_launch_anchor_record, test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor
- only in current: test_get_tab_orders_lock_reap_launch_anchor_record, test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor, _patch_launch_mechanics

### dev/tests/test_chromium_process.py
- only in base: test_wait_for_devtools_port_reads_real_port_file, test_wait_for_devtools_port_times_out_when_file_never_appears, test_build_self_launch_flags_keeps_gpu_on_under_stealth, test_build_self_launch_flags_includes_window_size_when_viewport_set, test_pids_on_profile_parses_pgrep_output, test_pids_on_profile_empty_when_no_match, test_kill_by_profile_delegates_to_death_pipe_terminate_then_kill, test_kill_by_profile_noop_when_no_pids, test_reap_orphaned_scrapes_kills_only_pids_older_than_budget, test_reap_orphaned_scrapes_never_kills_pid_under_budget_even_if_only_candidate, test_reap_orphaned_scrapes_sweeps_dirs_with_no_live_process
- only in current: ImportFrom@6, test_wait_for_devtools_port_reads_real_port_file, test_wait_for_devtools_port_times_out_when_file_never_appears, test_build_self_launch_flags_keeps_gpu_on_under_stealth, test_build_self_launch_flags_includes_window_size_when_viewport_set, test_pids_on_profile_parses_pgrep_output, test_pids_on_profile_empty_when_no_match, test_kill_by_profile_delegates_to_death_pipe_terminate_then_kill, test_kill_by_profile_noop_when_no_pids, test_reap_orphaned_scrapes_kills_only_pids_older_than_budget, test_reap_orphaned_scrapes_never_kills_pid_under_budget_even_if_only_candidate, test_reap_orphaned_scrapes_sweeps_dirs_with_no_live_process

### dev/tests/test_chromium_scrape_document_status.py
- only in base: test_try_scrape_calls_reap_orphaned_scrapes_at_start
- only in current: test_try_scrape_calls_reap_orphaned_scrapes_at_start

### dev/tests/test_chromium_scrape_facts.py
- only in base: test_cdp_headed_teardown_fires_on_exception, test_cdp_headed_teardown_fires_on_budget_timeout, test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir
- only in current: test_cdp_headed_teardown_fires_on_exception, test_cdp_headed_teardown_fires_on_budget_timeout, test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir

### dev/tests/test_death_pipe.py
- only in base: test_spawn_watchdog_returns_none_when_nothing_to_protect, test_watchdog_kills_dummy_process_once_write_end_closes, test_watchdog_removes_cleanup_dir_once_write_end_closes, test_watchdog_is_silent_noop_when_target_already_dead, test_watchdog_logs_intervention_when_it_actually_kills_something, test_terminate_then_kill_returns_pids_that_died_gracefully, test_terminate_then_kill_force_kills_survivors, test_terminate_then_kill_skips_already_dead_pid
- only in current: Import@11, test_spawn_watchdog_returns_none_when_nothing_to_protect, test_watchdog_kills_dummy_process_once_write_end_closes, test_watchdog_removes_cleanup_dir_once_write_end_closes, test_watchdog_is_silent_noop_when_target_already_dead, test_watchdog_logs_intervention_when_it_actually_kills_something, test_terminate_then_kill_returns_pids_that_died_gracefully, test_terminate_then_kill_force_kills_survivors, test_terminate_then_kill_skips_already_dead_pid

### dev/tests/test_death_pipe_tripwires.py
- only in base: _run_main
- only in current: _run_main

### dev/tests/test_drop_reporting.py
- only in base: test_onward_link_identity_logs_malformed_url, test_onward_link_identity_hostless_stays_silent
- only in current: test_onward_link_identity_logs_malformed_url, test_onward_link_identity_hostless_stays_silent

### dev/tests/test_google_goto_drops.py
- only in base: test_search_with_reason_attaches_goto_resolution_to_diagnosis
- only in current: test_search_with_reason_attaches_goto_resolution_to_diagnosis

### dev/tests/test_index_scrapes.py
- only in base: _write_sidecar, test_write_collection_file_matches_convention, test_index_one_success
- only in current: test_write_collection_file_matches_convention, test_index_one_success, _write_sidecar

### dev/tests/test_openalex_engine.py
- only in base: ImportFrom@4, test_429_carries_http_status_but_reason_stays_none, test_403_stays_plain_empty_no_reason_but_carries_http_status, test_success_with_results_has_no_diagnosis, test_success_with_zero_results_carries_http_status, test_api_key_sent_when_env_var_set, test_api_key_absent_when_env_var_unset, test_per_page_clamped_to_100, test_per_page_untouched_when_under_cap, test_search_base_method_returns_plain_list, test_search_base_method_propagates_exception
- only in current: ImportFrom@5, test_429_carries_http_status_but_reason_stays_none, test_403_stays_plain_empty_no_reason_but_carries_http_status, test_success_with_results_has_no_diagnosis, test_success_with_zero_results_carries_http_status, test_api_key_sent_when_env_var_set, test_api_key_absent_when_env_var_unset, test_per_page_clamped_to_100, test_per_page_untouched_when_under_cap, test_search_with_reason_returns_results_with_pdf_url, test_search_with_reason_propagates_exception

### dev/tests/test_pipe_scraper.py
- only in base: test_scrape_all_threads_headed_into_build_configs, test_scrape_all_default_headed_is_false, test_scrape_one_exception_becomes_tripwire_record
- only in current: test_scrape_all_threads_headed_into_build_configs, test_scrape_all_default_headed_is_false, test_scrape_one_exception_becomes_tripwire_record

### dev/tests/test_pipe_scraper_camoufox_engine.py
- only in base: test_scrape_all_camoufox_engine_dispatches_to_try_scrape_camoufox
- only in current: test_scrape_all_camoufox_engine_dispatches_to_try_scrape_camoufox

### dev/tests/test_pipe_scraper_config.py
- only in base: test_extract_pipe_config_stamp_reads_real_objects, test_extract_pipe_config_stamp_reads_anti_bot_fields_off_real_objects, test_build_configs_sets_fixed_anti_bot_posture, test_build_configs_produces_live_stealth_adapter, test_build_configs_default_stays_headless, test_build_configs_headed_true_sets_headless_false, test_build_configs_headed_does_not_change_anti_bot_posture, test_extract_pipe_config_stamp_reflects_headed
- only in current: test_extract_pipe_config_stamp_reads_real_objects, test_extract_pipe_config_stamp_reads_anti_bot_fields_off_real_objects, test_build_configs_sets_fixed_anti_bot_posture, test_build_configs_produces_live_stealth_adapter, test_build_configs_default_stays_headless, test_build_configs_headed_true_sets_headless_false, test_build_configs_headed_does_not_change_anti_bot_posture, test_extract_pipe_config_stamp_reflects_headed

### dev/tests/test_pipe_scraper_onward_links.py
- only in base: ImportFrom@9, ImportFrom@10, test_onward_link_identity_strips_query_and_fragment, test_onward_link_identity_lowercases_scheme_and_host, test_onward_link_identity_collapses_query_variants_to_one_key, test_onward_link_identity_none_for_hostless_url, test_collect_onward_links_excludes_urls_already_in_the_input_list, test_collect_onward_links_excludes_input_url_regardless_of_its_own_query_string, test_collect_onward_links_dedups_across_pages_order_preserving, test_collect_onward_links_ignores_results_with_no_links_key, test_collect_onward_links_returns_none_for_camoufox_engine, test_write_onward_links_file_writes_one_url_per_line, test_write_onward_links_file_writes_empty_file_for_empty_list, test_write_onward_links_file_writes_nothing_when_none, test_print_summary_reports_onward_link_count, test_print_summary_reports_camoufox_cannot_collect_not_a_bare_zero
- only in current: ImportFrom@10, ImportFrom@11, test_onward_link_identity_strips_query_and_fragment, test_onward_link_identity_lowercases_scheme_and_host, test_onward_link_identity_collapses_query_variants_to_one_key, test_onward_link_identity_none_for_hostless_url, test_collect_onward_links_excludes_urls_already_in_the_input_list, test_collect_onward_links_excludes_input_url_regardless_of_its_own_query_string, test_collect_onward_links_dedups_across_pages_order_preserving, test_collect_onward_links_ignores_results_with_no_links_key, test_collect_onward_links_returns_none_for_camoufox_engine, test_write_onward_links_file_writes_one_url_per_line, test_write_onward_links_file_writes_empty_file_for_empty_list, test_write_onward_links_file_writes_nothing_when_none, test_print_summary_reports_onward_link_count, test_print_summary_reports_camoufox_cannot_collect_not_a_bare_zero

### dev/tests/test_platform_optional_attributes.py
- only in base: ImportFrom@5, test_scrape_only_preamble_exits_for_platform_without_support, test_scrape_only_preamble_passes_for_supporting_platform
- only in current: ImportFrom@6, test_scrape_only_preamble_exits_for_platform_without_support, test_scrape_only_preamble_passes_for_supporting_platform

### dev/tests/test_proxy_riding_abort.py
- only in base: test_abort_stall_writes_no_job_md_on_reporter_failure
- only in current: test_abort_stall_writes_no_job_md_on_reporter_failure

### dev/tests/test_riding_sigint_report.py
- only in base: test_abort_interrupted_sigint, test_abort_interrupted_sigterm
- only in current: Import@3, test_abort_interrupted_sigint, test_abort_interrupted_sigterm

### dev/tests/test_riding_tail_race.py
- only in base: test_1_surplus_slots_race_both_done, test_2_write_exactly_once_per_url, test_3a_stale_url_skipped, test_3b_raced_fail_not_requeued, test_4_normal_path_no_racing, test_5_fail_before_success_done_once
- only in current: test_1_surplus_slots_race_both_done, test_2_write_exactly_once_per_url, test_3a_stale_url_skipped, test_3b_raced_fail_not_requeued, test_4_normal_path_no_racing, test_5_fail_before_success_done_once

### dev/tests/test_riding_watchdog.py
- only in base: test_6_watchdog_wedge_after_all_resolved, test_7_watchdog_pool_refresh
- only in current: Import@3, test_6_watchdog_wedge_after_all_resolved, test_7_watchdog_pool_refresh

### dev/tests/test_search_control_flow_removals.py
- only in base: test_extract_value_raises_when_the_cdp_result_has_no_value, test_extract_value_raises_on_a_non_dict_result
- only in current: ImportFrom@18, test_extract_value_raises_when_the_cdp_result_has_no_value, test_extract_value_raises_on_a_non_dict_result

### dev/tests/test_search_web_degraded_notice.py
- only in base: ImportFrom@1, test_prepend_puts_notice_before_breakdown_not_after, test_prepend_is_byte_identical_to_breakdown_alone_on_healthy_run
- only in current: ImportFrom@2, test_prepend_puts_notice_before_breakdown_not_after, test_prepend_is_byte_identical_to_breakdown_alone_on_healthy_run

### dev/tests/test_seed_feeders.py
- only in base: ImportFrom@3, test_robots_feeder_against_fixture_collects_allow_and_disallow, test_sitemap_feeder_against_fixture_resolves_two_level_nested_index, test_navtree_feeder_against_fixture_unions_versions_and_recovers_oldest_only_pages, test_navtree_feeder_against_fixture_detects_rsc_app_router_shape
- only in current: ImportFrom@4, ImportFrom@5, ImportFrom@6, test_robots_feeder_against_fixture_collects_allow_and_disallow, test_sitemap_feeder_against_fixture_resolves_two_level_nested_index, test_navtree_feeder_against_fixture_unions_versions_and_recovers_oldest_only_pages, test_navtree_feeder_against_fixture_detects_rsc_app_router_shape

### dev/tests/test_seed_feeders_navtree.py
- only in base: ImportFrom@11, test_navtree_feeder_workflow_next_data_shape_end_to_end, test_navtree_feeder_workflow_rsc_tree_shape_does_not_fall_through, test_navtree_feeder_workflow_rsc_dom_only_shape_falls_back_to_flat_tier, test_navtree_feeder_workflow_neither_shape_is_ok_empty, test_navtree_feeder_workflow_unreachable_seed_is_failed_not_ok_empty, test_navtree_feeder_workflow_invalid_seed_url_is_failed_not_empty, test_navtree_feeder_workflow_network_error_is_failed_with_error, test_navtree_feeder_workflow_malformed_next_data_is_failed_with_error
- only in current: ImportFrom@12, test_navtree_feeder_workflow_next_data_shape_end_to_end, test_navtree_feeder_workflow_rsc_tree_shape_does_not_fall_through, test_navtree_feeder_workflow_rsc_dom_only_shape_falls_back_to_flat_tier, test_navtree_feeder_workflow_neither_shape_is_ok_empty, test_navtree_feeder_workflow_unreachable_seed_is_failed_not_ok_empty, test_navtree_feeder_workflow_invalid_seed_url_is_failed_not_empty, test_navtree_feeder_workflow_network_error_is_failed_with_error, test_navtree_feeder_workflow_malformed_next_data_is_failed_with_error

### dev/tests/test_seed_feeders_robots.py
- only in base: ImportFrom@6, test_robots_feeder_workflow_returns_scoped_paths, test_robots_feeder_workflow_missing_robots_is_ok_empty, test_robots_feeder_workflow_invalid_seed_url_is_failed_not_empty, test_robots_feeder_workflow_network_error_is_failed_with_error
- only in current: ImportFrom@7, test_robots_feeder_workflow_returns_scoped_paths, test_robots_feeder_workflow_missing_robots_is_ok_empty, test_robots_feeder_workflow_invalid_seed_url_is_failed_not_empty, test_robots_feeder_workflow_network_error_is_failed_with_error

### dev/tests/test_seed_feeders_sitemap.py
- only in base: ImportFrom@9, test_sitemap_feeder_workflow_prefers_robots_declared_sitemap, test_sitemap_feeder_workflow_falls_back_to_conventional_paths, test_sitemap_feeder_workflow_all_404_is_ok_empty_docs_github_shape, test_sitemap_feeder_workflow_drops_foreign_host_urls, test_sitemap_feeder_workflow_non_xml_sitemap_is_failed_with_error, test_sitemap_feeder_workflow_declared_route_is_named_in_source, test_sitemap_feeder_workflow_conventional_route_is_named_in_source, test_sitemap_feeder_workflow_server_error_is_failed_not_empty
- only in current: ImportFrom@10, test_sitemap_feeder_workflow_prefers_robots_declared_sitemap, test_sitemap_feeder_workflow_falls_back_to_conventional_paths, test_sitemap_feeder_workflow_all_404_is_ok_empty_docs_github_shape, test_sitemap_feeder_workflow_drops_foreign_host_urls, test_sitemap_feeder_workflow_non_xml_sitemap_is_failed_with_error, test_sitemap_feeder_workflow_declared_route_is_named_in_source, test_sitemap_feeder_workflow_conventional_route_is_named_in_source, test_sitemap_feeder_workflow_server_error_is_failed_not_empty

### dev/tests/test_snippet.py
- only in base: ImportFrom@4, test_truncate_leaves_short_text_untouched, test_truncate_cuts_at_sentence_period_without_ellipsis, test_truncate_without_period_cuts_at_word_and_appends_ellipsis, test_truncate_without_spaces_hard_cuts_and_appends_ellipsis
- only in current: ImportFrom@5, ImportFrom@6, test_truncate_leaves_short_text_untouched, test_truncate_cuts_at_sentence_period_without_ellipsis, test_truncate_without_period_cuts_at_word_and_appends_ellipsis, test_truncate_without_spaces_hard_cuts_and_appends_ellipsis

### dev/tests/test_theblock_clean_pass.py
- only in base: ImportFrom@7, Assign@19, Assign@20, test_good_article_clean_file_written, test_bodyless_no_clean_file_url_recorded, test_raw_files_unchanged_after_pass, test_stats_correct, test_empty_entries_returns_zero_stats, test_bodyless_urls_union_merged, test_missing_raw_file_raises
- only in current: ImportFrom@8, Assign@13, Assign@14, test_good_article_clean_file_written, test_bodyless_no_clean_file_url_recorded, test_raw_files_unchanged_after_pass, test_stats_correct, test_empty_entries_returns_zero_stats, test_bodyless_urls_union_merged, test_missing_raw_file_raises

### dev/tests/test_theblock_discover.py
- only in base: _make_urls, Assign@15
- only in current: Assign@8

### dev/tests/test_yandex_engine.py
- only in base: ImportFrom@12, test_marker_word_in_own_query_no_longer_discards_real_results, test_genuine_showcaptcha_redirect_still_yields_no_results
- only in current: ImportFrom@13, test_marker_word_in_own_query_no_longer_discards_real_results, test_genuine_showcaptcha_redirect_still_yields_no_results

### dev/url_discovery/01_resume_state_probe.py
- only in base: url_discovery_probe_workflow
- only in current: url_discovery_probe_workflow, _run_experiments, _print_report

### dev/url_discovery/02_fixture_site_server.py
- only in base: If@31
- only in current: main, If@40

