# 07_inline_equivalence report

base: 7bb68ff2199531fdd4487e716526db4f600cde6d

files compared: 292
files with extraction helpers: 125
helpers checked: 408
files with problems: 38

## Files with problems

### dev/search_pipeline/01_google_smoke.py
- run_smoke_test: inlined body differs from base
- run_query: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/search_pipeline/04_ddg_smoke.py
- run_smoke_test: inlined body differs from base
- run_query: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/search_pipeline/05_search_smoke.py
- run_smoke: inlined body differs from base
- _run_query: inlined body differs from base
- only in base: 5 top-level nodes
- only in current: 5 top-level nodes

### dev/search_pipeline/08_scholar_smoke.py
- run_smoke_test: inlined body differs from base
- run_query: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/search_pipeline/09_openalex_smoke.py
- run_smoke_test: inlined body differs from base
- run_query: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/search_pipeline/12_max_results_probe.py
- run_probe: inlined body differs from base
- probe_single: inlined body differs from base
- only in base: 4 top-level nodes
- only in current: 4 top-level nodes

### dev/search_pipeline/no_google_burst_smoke.py
- run_smoke: inlined body differs from base
- only in base: 3 top-level nodes
- only in current: 3 top-level nodes

### dev/tests/_chromium_scrape_fakes.py
- _patch_cdp_launch_mechanics: inlined body differs from base

### dev/tests/conftest.py
- _no_real_browser_launch: inlined body differs from base

### dev/tests/test_brave_engine.py
- test_marker_word_from_own_query_no_longer_discards_real_results: inlined body differs from base
- test_marker_word_in_unrelated_organic_snippet_no_longer_discards_real_results: inlined body differs from base
- test_genuine_pow_link_block_still_yields_no_results: inlined body differs from base
- test_unrelated_button_before_containers_never_leaks_into_success_diagnosis: inlined body differs from base
- test_light_dom_challenge_button_is_solved_and_returns_real_results: inlined body differs from base
- test_shadow_dom_challenge_button_is_solved_and_returns_real_results: inlined body differs from base
- test_stuck_challenge_gives_up_within_budget_and_records_it_was_attempted: inlined body differs from base
- test_pow_link_with_clickable_button_solves_challenge_instead_of_giving_up: inlined body differs from base
- test_real_no_challenge_fixture_never_attempts_a_click: inlined body differs from base
- test_stuck_challenge_cancelled_mid_loop_leaves_partial_facts_behind: inlined body differs from base
- only in base: 1 top-level nodes

### dev/tests/test_browser.py
- test_reap_session_profile_kills_parsed_pids_and_cleans_leftover_directories: inlined body differs from base
- test_reap_session_profile_no_survivors_still_cleans_leftover_directories: inlined body differs from base
- test_kill_own_chrome_full_teardown_sequence: inlined body differs from base
- test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises: inlined body differs from base
- only in base: 3 top-level nodes

### dev/tests/test_browser_get_tab.py
- _patch_launch_mechanics: inlined body differs from base
- test_get_tab_orders_lock_reap_launch_anchor_record: inlined body differs from base
- test_get_tab_spawns_focus_watchdog_with_owned_pids_and_anchor: inlined body differs from base

### dev/tests/test_chromium_process.py
- test_wait_for_devtools_port_reads_real_port_file: inlined body differs from base
- test_wait_for_devtools_port_times_out_when_file_never_appears: inlined body differs from base
- test_build_self_launch_flags_keeps_gpu_on_under_stealth: inlined body differs from base
- test_build_self_launch_flags_includes_window_size_when_viewport_set: inlined body differs from base
- test_pids_on_profile_parses_pgrep_output: inlined body differs from base
- test_pids_on_profile_empty_when_no_match: inlined body differs from base
- test_kill_by_profile_delegates_to_death_pipe_terminate_then_kill: inlined body differs from base
- test_kill_by_profile_noop_when_no_pids: inlined body differs from base
- test_reap_orphaned_scrapes_kills_only_pids_older_than_budget: inlined body differs from base
- test_reap_orphaned_scrapes_never_kills_pid_under_budget_even_if_only_candidate: inlined body differs from base
- test_reap_orphaned_scrapes_sweeps_dirs_with_no_live_process: inlined body differs from base
- only in current: 1 top-level nodes

### dev/tests/test_chromium_scrape_document_status.py
- test_try_scrape_calls_reap_orphaned_scrapes_at_start: inlined body differs from base

### dev/tests/test_chromium_scrape_facts.py
- test_cdp_headed_teardown_fires_on_exception: inlined body differs from base
- test_cdp_headed_teardown_fires_on_budget_timeout: inlined body differs from base
- test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir: inlined body differs from base

### dev/tests/test_death_pipe.py
- test_spawn_watchdog_returns_none_when_nothing_to_protect: inlined body differs from base
- test_watchdog_kills_dummy_process_once_write_end_closes: inlined body differs from base
- test_watchdog_removes_cleanup_dir_once_write_end_closes: inlined body differs from base
- test_watchdog_is_silent_noop_when_target_already_dead: inlined body differs from base
- test_watchdog_logs_intervention_when_it_actually_kills_something: inlined body differs from base
- test_terminate_then_kill_returns_pids_that_died_gracefully: inlined body differs from base
- test_terminate_then_kill_force_kills_survivors: inlined body differs from base
- test_terminate_then_kill_skips_already_dead_pid: inlined body differs from base
- only in current: 1 top-level nodes

### dev/tests/test_death_pipe_tripwires.py
- _run_main: inlined body differs from base

### dev/tests/test_drop_reporting.py
- test_onward_link_identity_logs_malformed_url: inlined body differs from base
- test_onward_link_identity_hostless_stays_silent: inlined body differs from base

### dev/tests/test_google_goto_drops.py
- test_search_with_reason_attaches_goto_resolution_to_diagnosis: inlined body differs from base

### dev/tests/test_index_scrapes.py
- _write_sidecar: inlined body differs from base
- test_write_collection_file_matches_convention: inlined body differs from base
- test_index_one_success: inlined body differs from base

### dev/tests/test_openalex_engine.py
- test_429_carries_http_status_but_reason_stays_none: inlined body differs from base
- test_403_stays_plain_empty_no_reason_but_carries_http_status: inlined body differs from base
- test_success_with_results_has_no_diagnosis: inlined body differs from base
- test_success_with_zero_results_carries_http_status: inlined body differs from base
- test_api_key_sent_when_env_var_set: inlined body differs from base
- test_api_key_absent_when_env_var_unset: inlined body differs from base
- test_per_page_clamped_to_100: inlined body differs from base
- test_per_page_untouched_when_under_cap: inlined body differs from base
- only in base: 3 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_pipe_scraper.py
- test_scrape_all_threads_headed_into_build_configs: inlined body differs from base
- test_scrape_all_default_headed_is_false: inlined body differs from base
- test_scrape_one_exception_becomes_tripwire_record: inlined body differs from base

### dev/tests/test_pipe_scraper_camoufox_engine.py
- test_scrape_all_camoufox_engine_dispatches_to_try_scrape_camoufox: inlined body differs from base

### dev/tests/test_pipe_scraper_config.py
- test_extract_pipe_config_stamp_reads_real_objects: inlined body differs from base
- test_extract_pipe_config_stamp_reads_anti_bot_fields_off_real_objects: inlined body differs from base
- test_build_configs_sets_fixed_anti_bot_posture: inlined body differs from base
- test_build_configs_produces_live_stealth_adapter: inlined body differs from base
- test_build_configs_default_stays_headless: inlined body differs from base
- test_build_configs_headed_true_sets_headless_false: inlined body differs from base
- test_build_configs_headed_does_not_change_anti_bot_posture: inlined body differs from base
- test_extract_pipe_config_stamp_reflects_headed: inlined body differs from base

### dev/tests/test_pipe_scraper_onward_links.py
- test_onward_link_identity_strips_query_and_fragment: inlined body differs from base
- test_onward_link_identity_lowercases_scheme_and_host: inlined body differs from base
- test_onward_link_identity_collapses_query_variants_to_one_key: inlined body differs from base
- test_onward_link_identity_none_for_hostless_url: inlined body differs from base
- test_collect_onward_links_excludes_urls_already_in_the_input_list: inlined body differs from base
- test_collect_onward_links_excludes_input_url_regardless_of_its_own_query_string: inlined body differs from base
- test_collect_onward_links_dedups_across_pages_order_preserving: inlined body differs from base
- test_collect_onward_links_ignores_results_with_no_links_key: inlined body differs from base
- test_collect_onward_links_returns_none_for_camoufox_engine: inlined body differs from base
- test_write_onward_links_file_writes_one_url_per_line: inlined body differs from base
- test_write_onward_links_file_writes_empty_file_for_empty_list: inlined body differs from base
- test_write_onward_links_file_writes_nothing_when_none: inlined body differs from base
- test_print_summary_reports_onward_link_count: inlined body differs from base
- test_print_summary_reports_camoufox_cannot_collect_not_a_bare_zero: inlined body differs from base
- only in base: 2 top-level nodes
- only in current: 2 top-level nodes

### dev/tests/test_platform_optional_attributes.py
- test_scrape_only_preamble_exits_for_platform_without_support: inlined body differs from base
- test_scrape_only_preamble_passes_for_supporting_platform: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_proxy_riding_abort.py
- test_abort_stall_writes_no_job_md_on_reporter_failure: inlined body differs from base

### dev/tests/test_riding_sigint_report.py
- test_abort_interrupted_sigint: inlined body differs from base
- test_abort_interrupted_sigterm: inlined body differs from base
- only in current: 1 top-level nodes

### dev/tests/test_riding_tail_race.py
- test_1_surplus_slots_race_both_done: inlined body differs from base
- test_2_write_exactly_once_per_url: inlined body differs from base
- test_3a_stale_url_skipped: inlined body differs from base
- test_3b_raced_fail_not_requeued: inlined body differs from base
- test_4_normal_path_no_racing: inlined body differs from base
- test_5_fail_before_success_done_once: inlined body differs from base

### dev/tests/test_riding_watchdog.py
- test_6_watchdog_wedge_after_all_resolved: inlined body differs from base
- test_7_watchdog_pool_refresh: inlined body differs from base
- only in current: 1 top-level nodes

### dev/tests/test_search_control_flow_removals.py
- test_extract_value_raises_when_the_cdp_result_has_no_value: inlined body differs from base
- test_extract_value_raises_on_a_non_dict_result: inlined body differs from base
- only in current: 1 top-level nodes

### dev/tests/test_search_web_degraded_notice.py
- test_prepend_puts_notice_before_breakdown_not_after: inlined body differs from base
- test_prepend_is_byte_identical_to_breakdown_alone_on_healthy_run: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_seed_feeders.py
- test_robots_feeder_against_fixture_collects_allow_and_disallow: inlined body differs from base
- test_sitemap_feeder_against_fixture_resolves_two_level_nested_index: inlined body differs from base
- test_navtree_feeder_against_fixture_unions_versions_and_recovers_oldest_only_pages: inlined body differs from base
- test_navtree_feeder_against_fixture_detects_rsc_app_router_shape: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 3 top-level nodes

### dev/tests/test_seed_feeders_navtree.py
- test_navtree_feeder_workflow_next_data_shape_end_to_end: inlined body differs from base
- test_navtree_feeder_workflow_rsc_tree_shape_does_not_fall_through: inlined body differs from base
- test_navtree_feeder_workflow_rsc_dom_only_shape_falls_back_to_flat_tier: inlined body differs from base
- test_navtree_feeder_workflow_neither_shape_is_ok_empty: inlined body differs from base
- test_navtree_feeder_workflow_unreachable_seed_is_failed_not_ok_empty: inlined body differs from base
- test_navtree_feeder_workflow_invalid_seed_url_is_failed_not_empty: inlined body differs from base
- test_navtree_feeder_workflow_network_error_is_failed_with_error: inlined body differs from base
- test_navtree_feeder_workflow_malformed_next_data_is_failed_with_error: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_seed_feeders_robots.py
- test_robots_feeder_workflow_returns_scoped_paths: inlined body differs from base
- test_robots_feeder_workflow_missing_robots_is_ok_empty: inlined body differs from base
- test_robots_feeder_workflow_invalid_seed_url_is_failed_not_empty: inlined body differs from base
- test_robots_feeder_workflow_network_error_is_failed_with_error: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_seed_feeders_sitemap.py
- test_sitemap_feeder_workflow_prefers_robots_declared_sitemap: inlined body differs from base
- test_sitemap_feeder_workflow_falls_back_to_conventional_paths: inlined body differs from base
- test_sitemap_feeder_workflow_all_404_is_ok_empty_docs_github_shape: inlined body differs from base
- test_sitemap_feeder_workflow_drops_foreign_host_urls: inlined body differs from base
- test_sitemap_feeder_workflow_non_xml_sitemap_is_failed_with_error: inlined body differs from base
- test_sitemap_feeder_workflow_declared_route_is_named_in_source: inlined body differs from base
- test_sitemap_feeder_workflow_conventional_route_is_named_in_source: inlined body differs from base
- test_sitemap_feeder_workflow_server_error_is_failed_not_empty: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

### dev/tests/test_snippet.py
- test_truncate_leaves_short_text_untouched: inlined body differs from base
- test_truncate_cuts_at_sentence_period_without_ellipsis: inlined body differs from base
- test_truncate_without_period_cuts_at_word_and_appends_ellipsis: inlined body differs from base
- test_truncate_without_spaces_hard_cuts_and_appends_ellipsis: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 2 top-level nodes

### dev/tests/test_yandex_engine.py
- test_marker_word_in_own_query_no_longer_discards_real_results: inlined body differs from base
- test_genuine_showcaptcha_redirect_still_yields_no_results: inlined body differs from base
- only in base: 1 top-level nodes
- only in current: 1 top-level nodes

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

