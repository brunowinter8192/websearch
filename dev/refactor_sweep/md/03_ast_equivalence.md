# 03_ast_equivalence report

base: d225306d39d61dbca5eba1b24f26699dd3847502

files compared: 41
top-level node multiset identical: 0
top-level node multiset differs: 41

## Files that differ

### dev/access_recovery/_dom.py
- only in base: extract_value
- only in current: Import@2, extract_value

### dev/brave_return/_brave_probe_query.py
- only in base: _extract_value
- only in current: Import@2, _extract_value

### dev/browser_posture/_lib.py
- only in base: extract_value
- only in current: Import@2, extract_value

### dev/explore_pipeline/05_playwright_bfs.py
- only in base: _format_key_url_and_baseline
- only in current: _format_key_url_and_baseline

### dev/mojeek_return/_mojeek_pydoll_probe_core.py
- only in base: _decode_altcha_payload
- only in current: Import@2, _decode_altcha_payload

### dev/mojeek_return/_mojeek_pydoll_probe_query.py
- only in base: _extract_value
- only in current: Import@2, _extract_value

### dev/mojeek_return/mojeek_challenge_capture.py
- only in base: _extract_value
- only in current: Import@2, _extract_value

### dev/news_pipeline/01_coindesk_discover.py
- only in base: _extract_section, parse_url_date
- only in current: _extract_section, parse_url_date

### dev/news_pipeline/exploration/01_coindesk_ui_probe.py
- only in base: parse_url_date
- only in current: parse_url_date

### dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py
- only in base: _extract_section, parse_url_date
- only in current: _extract_section, parse_url_date

### dev/news_pipeline/exploration/06_coindesk_full_discovery.py
- only in base: try_rewarm
- only in current: try_rewarm

### dev/news_pipeline/exploration/_04_replay.py
- only in base: extract_json_sample
- only in current: extract_json_sample

### dev/news_pipeline/exploration/_05_report.py
- only in base: _render_target_section, _render_walk_call_row, _render_fixed_call_row
- only in current: _render_target_section, _render_walk_call_row, _render_fixed_call_row

### dev/news_pipeline/exploration/_05b_report.py
- only in base: _render_ladder_section, _render_feedpage_section
- only in current: _render_ladder_section, _render_feedpage_section

### dev/news_pipeline/exploration/_06_report.py
- only in base: write_report
- only in current: write_report

### dev/news_pipeline/theblock/probe_curated_theblock_cf.py
- only in base: probe_curated_theblock_cf_workflow, check_proxy
- only in current: Assign@19, probe_curated_theblock_cf_workflow, _print_rejections, check_proxy

### dev/news_pipeline/theblock/probe_repo_cf_survey.py
- only in base: probe_repo_cf_survey_workflow, check_proxy
- only in current: Assign@20, probe_repo_cf_survey_workflow, _print_rejections, check_proxy

### dev/scrape_pipeline/05_paper_mode/download.py
- only in base: download_workflow
- only in current: download_workflow

### dev/scrape_pipeline/06_cloudflare_md_adoption.py
- only in base: format_table
- only in current: format_table

### dev/scrape_pipeline/_pipe_scrape_eval_phase1.py
- only in base: phase1_concurrency_sweep, fmt_sweep_row
- only in current: phase1_concurrency_sweep, fmt_sweep_row

### dev/scrape_pipeline/_pipe_scrape_eval_phase2.py
- only in base: write_phase2_report
- only in current: write_phase2_report

### dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py
- only in base: build_fix1_section, build_fix2_section
- only in current: build_fix1_section, build_fix2_section

### dev/search_pipeline/24_pydoll_teardown_verify.py
- only in base: _count_renderers
- only in current: _count_renderers

### dev/search_pipeline/_capture_sorry.py
- only in base: stop_browser
- only in current: stop_browser

### dev/search_pipeline/bee_probes/acquire_probe.py
- only in base: _run_single_query
- only in current: _run_single_query

### dev/search_pipeline/bee_probes/branch_probe.py
- only in base: _write_stop_note, _run_single_query
- only in current: _write_stop_note, _run_single_query

### dev/search_pipeline/bee_probes/cdp_starvation_probe.py
- only in base: _run_single_query
- only in current: _run_single_query

### dev/search_pipeline/browser_probes/25_startpage_probe.py
- only in base: _extract_value
- only in current: _extract_value

### dev/search_pipeline/browser_probes/26_brave_probe.py
- only in base: _extract_value
- only in current: _extract_value

### dev/search_pipeline/browser_probes/27_brave_headed_lane_probe.py
- only in base: _extract_value
- only in current: _extract_value

### dev/search_pipeline/browser_probes/28_bing_probe.py
- only in base: _extract_value
- only in current: _extract_value

### dev/search_pipeline/browser_probes/29_yandex_probe.py
- only in base: _extract_value
- only in current: _extract_value

### dev/search_pipeline/browser_probes/_date_availability_probe_browser.py
- only in base: _extract_value
- only in current: Import@2, _extract_value

### dev/search_pipeline/domain_probes/20_docs_probe.py
- only in base: _run_docs_queries, _close_browser_quietly
- only in current: _run_docs_queries

### dev/search_pipeline/inspections/inspect_engine_dom.py
- only in base: _extract_value, _render_h1
- only in current: _extract_value, _render_h1

### dev/search_pipeline/pdf_probes/_download_classify_probe_report.py
- only in base: _section_per_url_detail
- only in current: _section_per_url_detail

### dev/search_pipeline/pydoll_fingerprint_probe.py
- only in base: _print_results_table, _print_key_signals, _extract_value
- only in current: _print_results_table, _print_key_signals, _extract_value

### dev/search_pipeline/report_analysis/engine_health_audit.py
- only in base: format_table, classify_health
- only in current: format_table, classify_health

### dev/search_pipeline/report_analysis/snippet_quality_analysis.py
- only in base: _render_url_details
- only in current: _render_url_details

### dev/search_pipeline/report_analysis/snippet_selection_simulator.py
- only in base: _render_per_query_picks
- only in current: _render_per_query_picks

### dev/search_pipeline/with_google_decoupling_smoke.py
- only in base: _write_report
- only in current: _write_report

